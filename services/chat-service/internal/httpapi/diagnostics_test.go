package httpapi_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http/httptest"
	"strings"
	"testing"

	"plotina/chat-service/internal/httpapi"
)

func TestReadiness(t *testing.T) {
	for _, failing := range []string{"", "database", "room_service"} {
		t.Run("failed="+failing, func(t *testing.T) {
			checks := make(map[string]httpapi.ReadinessCheck)
			for _, name := range []string{"database", "room_service"} {
				checks[name] = func(context.Context) error {
					if name == failing {
						return errors.New("secret-database-password")
					}
					return nil
				}
			}
			recorder := httptest.NewRecorder()
			httpapi.NewHandler(&stubService{}, httpapi.WithReadiness(checks)).ServeHTTP(recorder, httptest.NewRequest("GET", "/ready", nil))
			want := 200
			if failing != "" {
				want = 503
			}
			if recorder.Code != want || strings.Contains(recorder.Body.String(), "secret") {
				t.Fatalf("status=%d, body=%s", recorder.Code, recorder.Body.String())
			}
			var result struct {
				Status string
				Checks map[string]string
			}
			if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			for _, name := range []string{"database", "room_service"} {
				state := "ok"
				if name == failing {
					state = "unavailable"
				}
				if result.Checks[name] != state {
					t.Fatalf("unexpected checks: %+v", result)
				}
			}
		})
	}
}

func TestReadinessWithoutChecksDoesNotClaimSuccess(t *testing.T) {
	recorder := httptest.NewRecorder()
	httpapi.NewHandler(&stubService{}).ServeHTTP(recorder, httptest.NewRequest("GET", "/ready", nil))
	if recorder.Code != 503 {
		t.Fatalf("unconfigured readiness must not return success: %d", recorder.Code)
	}
}

func TestRequestDiagnosticsDoNotLogSecrets(t *testing.T) {
	var logs bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&logs, nil))
	handler := httpapi.NewHandler(&stubService{}, httpapi.WithLogger(logger))
	req := httptest.NewRequest("POST", "/rooms/room-1/messages?secret-query=value", strings.NewReader(`{"command_id":"c","text":"secret-message"}`))
	req.Header.Set("Authorization", "Bearer secret-token")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-ID", "gateway-request-1")
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, req)
	if recorder.Header().Get("X-Request-ID") != "gateway-request-1" {
		t.Fatal("request ID was not propagated")
	}
	var entry map[string]any
	if err := json.Unmarshal(logs.Bytes(), &entry); err != nil {
		t.Fatal(err)
	}
	if entry["route"] != "POST /rooms/{room_id}/messages" || entry["request_id"] != "gateway-request-1" || entry["status"] != float64(200) {
		t.Fatalf("invalid diagnostic entry: %s", logs.String())
	}
	if strings.Contains(logs.String(), "secret") || strings.Contains(logs.String(), "room-1") {
		t.Fatalf("request details leaked into log: %s", logs.String())
	}
	for _, invalidID := range []string{"", "bad request id", strings.Repeat("a", 65)} {
		req := httptest.NewRequest("GET", "/health", nil)
		req.Header.Set("X-Request-ID", invalidID)
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, req)
		if len(recorder.Header().Get("X-Request-ID")) != 32 {
			t.Fatal("invalid request ID must be replaced")
		}
	}
}
