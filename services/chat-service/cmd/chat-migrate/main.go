package main

import (
	"context"
	"log"
	"os"
	"time"

	"plotina/chat-service/internal/storage/postgres"
	"plotina/chat-service/migrations"
)

func main() {
	if err := run(); err != nil {
		log.Fatal(err)
	}
}

func run() error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	pool, err := postgres.Open(ctx, os.Getenv("CHAT_DATABASE_URL"))
	if err != nil {
		return err
	}
	defer pool.Close()
	if err := migrations.Apply(ctx, pool); err != nil {
		return err
	}
	log.Println("chat database migrations applied")
	return nil
}
