package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"plotina/chat-service/web"
)

func main() {
	addr := os.Getenv("CHAT_WEB_ADDR")
	if addr == "" {
		addr = "127.0.0.1:8099"
	}
	server := &http.Server{
		Addr: addr, Handler: web.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("chat preview: http://%s", addr)
	if err := server.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}
