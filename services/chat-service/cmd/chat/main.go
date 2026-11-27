package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/httpapi"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage/postgres"
)

func main() {
	if err := run(); err != nil {
		log.Fatal(err)
	}
}

func run() error {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	roomClient, err := rooms.NewHTTPClient(os.Getenv("ROOM_SERVICE_URL"), 3*time.Second)
	if err != nil {
		return fmt.Errorf("configure Room Service: %w", err)
	}
	connectCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	pool, err := postgres.Open(connectCtx, os.Getenv("CHAT_DATABASE_URL"))
	cancel()
	if err != nil {
		return err
	}
	defer pool.Close()
	repository := postgres.NewRepository(pool)
	checkCtx, checkCancel := context.WithTimeout(ctx, 5*time.Second)
	err = repository.CheckReady(checkCtx)
	checkCancel()
	if err != nil {
		return errors.New("Chat DB schema is not ready: check the database and run chat-migrate")
	}
	service := chat.NewService(roomClient, repository)
	addr := os.Getenv("HTTP_ADDR")
	if addr == "" {
		addr = ":8080"
	}

	server := &http.Server{
		Addr: addr,
		Handler: httpapi.NewHandler(service,
			httpapi.WithReadiness(map[string]httpapi.ReadinessCheck{
				"database":     repository.CheckReady,
				"room_service": roomClient.CheckHealth,
			}),
			httpapi.WithLogger(slog.New(slog.NewJSONHandler(os.Stdout, nil)))),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	log.Printf("chat service starting on %s", addr)
	serverErrors := make(chan error, 1)
	go func() { serverErrors <- server.ListenAndServe() }()
	select {
	case err := <-serverErrors:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			_ = server.Close()
			return fmt.Errorf("shutdown HTTP server: %w", err)
		}
		return nil
	}
}
