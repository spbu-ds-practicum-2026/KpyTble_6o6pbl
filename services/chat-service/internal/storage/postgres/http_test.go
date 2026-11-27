package postgres_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/httpapi"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage/postgres"
)

// Exercises real HTTP handlers, the Room Service HTTP client and PostgreSQL.
// Only Room Service itself is replaced by a local HTTP server.
func TestPostgresHTTPFlow(t *testing.T) {
	pool, newPool := setupDatabase(t)
	roomServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer valid-token" {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = fmt.Fprint(w, `{"error":{"code":"unauthorized","message":"Invalid token"}}`)
			return
		}
		_, _ = fmt.Fprint(w, `{"room_id":"room-1","participant_id":"participant-1","display_name":"Alice","role":"host","connected":true}`)
	}))
	defer roomServer.Close()
	client, err := rooms.NewHTTPClient(roomServer.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	handler := httpapi.NewHandler(chat.NewService(client, postgres.NewRepository(pool)))
	request := func(method, path, token, body string, status int) []byte {
		t.Helper()
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("Content-Type", "application/json")
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, req)
		if recorder.Code != status {
			t.Fatalf("%s %s: status=%d, body=%s", method, path, recorder.Code, recorder.Body.String())
		}
		return recorder.Body.Bytes()
	}
	path := "/rooms/room-1/messages"
	seqPath := path + "/seq"
	if data := request("GET", seqPath, "valid-token", "", 200); strings.TrimSpace(string(data)) != `{"messageSeq":0}` {
		t.Fatalf("unexpected initial sequence: %s", data)
	}
	payload := `{"command_id":"cmd-1","text":"Привет!"}`
	request("POST", path, "invalid-token", payload, 401)
	request("GET", seqPath, "invalid-token", "", 401)
	var first chat.SendResult
	if err := json.Unmarshal(request("POST", path, "valid-token", payload, 200), &first); err != nil {
		t.Fatal(err)
	}
	if first.Duplicate || first.Message.MessageSeq != 1 || first.Message.ParticipantID != "participant-1" {
		t.Fatalf("unexpected message: %+v", first)
	}
	pool.Close()
	pool = newPool()
	handler = httpapi.NewHandler(chat.NewService(client, postgres.NewRepository(pool)))
	var retry chat.SendResult
	if err := json.Unmarshal(request("POST", path, "valid-token", payload, 200), &retry); err != nil {
		t.Fatal(err)
	}
	if !retry.Duplicate || retry.Message != first.Message {
		t.Fatalf("retry after reopening database changed message: %+v", retry)
	}
	request("POST", path, "valid-token", `{"command_id":"cmd-1","text":"Другой текст"}`, 409)
	if data := request("GET", seqPath, "valid-token", "", 200); strings.TrimSpace(string(data)) != `{"messageSeq":1}` {
		t.Fatalf("retry or read changed sequence: %s", data)
	}
	// A stopped database pool must produce a sanitized dependency error.
	pool.Close()
	for _, method := range []string{"GET", "POST"} {
		endpoint := path
		if method == "GET" {
			endpoint = seqPath
		}
		data := request(method, endpoint, "valid-token", payload, 503)
		var body struct {
			Error struct{ Code string }
		}
		if err := json.Unmarshal(data, &body); err != nil || body.Error.Code != "storage_unavailable" {
			t.Fatalf("unexpected storage error: %s", data)
		}
	}
	roomServer.Close()
	// The dependency error is mapped without reaching the already closed DB.
	data := request("GET", seqPath, "valid-token", "", 503)
	if !strings.Contains(string(data), `"code":"room_service_unavailable"`) {
		t.Fatalf("unexpected Room Service error: %s", data)
	}
}
