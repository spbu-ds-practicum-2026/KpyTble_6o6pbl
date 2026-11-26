package httpapi

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"log/slog"
	"net/http"
	"time"
)

type ReadinessCheck func(context.Context) error

type Option func(*handler)

func WithReadiness(checks map[string]ReadinessCheck) Option {
	return func(h *handler) {
		h.checks = make(map[string]ReadinessCheck, len(checks))
		for name, check := range checks {
			h.checks[name] = check
		}
	}
}

func WithLogger(logger *slog.Logger) Option {
	return func(h *handler) { h.logger = logger }
}

func (h *handler) ready(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	type outcome struct {
		name string
		err  error
	}
	results := make(chan outcome, len(h.checks))
	for name, check := range h.checks {
		go func(name string, check ReadinessCheck) {
			results <- outcome{name, check(ctx)}
		}(name, check)
	}
	checks := make(map[string]string, len(h.checks))
	for name := range h.checks {
		checks[name] = "unavailable"
	}
	ok := len(h.checks) != 0
	for range h.checks {
		select {
		case result := <-results:
			if result.err != nil {
				ok = false
			} else {
				checks[result.name] = "ok"
			}
		case <-ctx.Done():
			ok = false
		}
	}
	status, state := http.StatusOK, "ok"
	if !ok {
		status, state = http.StatusServiceUnavailable, "not_ready"
	}
	writeJSON(w, status, map[string]any{"status": state, "checks": checks})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	if w.status == 0 {
		w.status = status
		w.ResponseWriter.WriteHeader(status)
	}
}

func (w *statusWriter) Write(data []byte) (int, error) {
	if w.status == 0 {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(data)
}

// ServeMux sets r.Pattern on the original request. Log that pattern instead of
// URLs, query strings, headers or message bodies, which may contain secrets.
func (h *handler) diagnostics(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		requestID := r.Header.Get("X-Request-ID")
		if !validRequestID(requestID) {
			var id [16]byte
			_, _ = rand.Read(id[:])
			requestID = hex.EncodeToString(id[:])
		}
		w.Header().Set("X-Request-ID", requestID)
		writer := &statusWriter{ResponseWriter: w}
		next.ServeHTTP(writer, r)
		if h.logger != nil {
			h.logger.Info("http_request", "request_id", requestID, "method", r.Method,
				"route", r.Pattern, "status", writer.status, "duration_ms", time.Since(started).Milliseconds())
		}
	})
}

func validRequestID(value string) bool {
	if len(value) == 0 || len(value) > 64 {
		return false
	}
	for _, char := range value {
		if !(char >= 'a' && char <= 'z' || char >= 'A' && char <= 'Z' ||
			char >= '0' && char <= '9' || char == '-' || char == '_') {
			return false
		}
	}
	return true
}
