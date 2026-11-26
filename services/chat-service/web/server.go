// Package web serves the standalone preview and embeddable chat widget assets.
package web

import (
	"embed"
	"net/http"
)

//go:embed index.html preview.css preview.js chat-widget.js chat-widget.css chat-client.js
var assets embed.FS

// Handler serves only embedded frontend assets; it does not proxy chat API calls.
func Handler() http.Handler {
	files := http.FileServer(http.FS(assets))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Cache-Control", "no-store")
		files.ServeHTTP(w, r)
	})
}
