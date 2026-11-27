package httpapi_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/httpapi"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage"
)

func TestHTTPMessageFlow(t *testing.T) {
	roomServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Header.Get("Authorization") {
		case "Bearer alice-token":
			if r.URL.Path != "/internal/rooms/room-1/membership" {
				w.WriteHeader(403)
				_, _ = fmt.Fprint(w, `{"error":{"code":"wrong_room","message":"Wrong room"}}`)
				return
			}
			_, _ = fmt.Fprint(w, `{"room_id":"room-1","participant_id":"participant-1","display_name":"Alice","role":"host","connected":true}`)
		default:
			w.WriteHeader(401)
			_, _ = fmt.Fprint(w, `{"error":{"code":"unauthorized","message":"Bad token"}}`)
		}
	}))
	defer roomServer.Close()
	roomClient, err := rooms.NewHTTPClient(roomServer.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(httpapi.NewHandler(chat.NewService(roomClient, storage.NewMemoryRepository())))
	defer server.Close()
	request := func(method, path, token, body string, status int) []byte {
		t.Helper()
		req, err := http.NewRequest(method, server.URL+path, strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer "+token)
		if method == http.MethodPost {
			req.Header.Set("Content-Type", "application/json")
		}
		response, err := server.Client().Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		data, err := io.ReadAll(response.Body)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != status || !strings.HasPrefix(response.Header.Get("Content-Type"), "application/json") {
			t.Fatalf("%s %s: status=%d, body=%s", method, path, response.StatusCode, data)
		}
		return data
	}
	seqPath := "/rooms/room-1/messages/seq"
	if body := request("GET", seqPath, "alice-token", "", 200); strings.TrimSpace(string(body)) != `{"messageSeq":0}` {
		t.Fatalf("unexpected empty sequence: %s", body)
	}
	for _, method := range []string{"GET", "POST"} {
		path := seqPath
		body := ""
		if method == "POST" {
			path = "/rooms/room-1/messages"
			body = `{"command_id":"cmd-1","text":"Привет!"}`
		}
		request(method, path, "invalid-token", body, 401)
		request(method, strings.Replace(path, "room-1", "room-2", 1), "alice-token", body, 403)
	}
	messagePath := "/rooms/room-1/messages"
	payload := `{"command_id":"cmd-1","text":"Привет!"}`
	var first chat.SendResult
	if err := json.Unmarshal(request("POST", messagePath, "alice-token", payload, 200), &first); err != nil {
		t.Fatal(err)
	}
	if first.Duplicate || first.CommandID != "cmd-1" || first.Message.ParticipantID != "participant-1" || first.Message.MessageSeq != 1 {
		t.Fatalf("unexpected response: %+v", first)
	}
	var retry chat.SendResult
	if err := json.Unmarshal(request("POST", messagePath, "alice-token", payload, 200), &retry); err != nil {
		t.Fatal(err)
	}
	if !retry.Duplicate || retry.Message != first.Message {
		t.Fatalf("retry changed message: first=%+v, retry=%+v", first, retry)
	}
	request("POST", messagePath, "alice-token", `{"command_id":"cmd-1","text":"Другой текст"}`, 409)
	if body := request("GET", seqPath, "alice-token", "", 200); strings.TrimSpace(string(body)) != `{"messageSeq":1}` {
		t.Fatalf("retry, conflict or read changed sequence: %s", body)
	}
}

type stubService struct {
	calls int
	err   error
}

func (s *stubService) SendMessage(context.Context, chat.SendCommand) (chat.SendResult, error) {
	s.calls++
	return chat.SendResult{}, s.err
}

func (s *stubService) GetChatSeq(context.Context, string, string) (chat.Sequence, error) {
	s.calls++
	return chat.Sequence{}, s.err
}

func TestHTTPRejectsInvalidRequestsBeforeServiceCall(t *testing.T) {
	tests := []struct {
		name, method, path, auth, contentType, body string
		status                                      int
	}{
		{"missing token", "POST", "/rooms/r/messages", "", "application/json", `{}`, 401},
		{"wrong scheme", "GET", "/rooms/r/messages/seq", "Basic abc", "", "", 401},
		{"empty bearer", "GET", "/rooms/r/messages/seq", "Bearer", "", "", 401},
		{"missing content type", "POST", "/rooms/r/messages", "Bearer t", "", `{}`, 415},
		{"invalid JSON", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{`, 422},
		{"invalid UTF8", "POST", "/rooms/r/messages", "Bearer t", "application/json", "{\"command_id\":\"c\",\"text\":\"\xff\"}", 422},
		{"missing field", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"text":"hi"}`, 422},
		{"null field", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":null}`, 422},
		{"null body", "POST", "/rooms/r/messages", "Bearer t", "application/json", `null`, 422},
		{"numeric text", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":42}`, 422},
		{"client author", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":"hi","participant_id":"fake"}`, 422},
		{"two objects", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":"hi"} {}`, 422},
		{"trailing garbage", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":"hi"}x`, 422},
		{"oversized", "POST", "/rooms/r/messages", "Bearer t", "application/json", `{"command_id":"c","text":"` + strings.Repeat("a", 64*1024) + `"}`, 413},
		{"wrong method", "DELETE", "/rooms/r/messages", "Bearer t", "", "", 405},
		{"unknown route", "GET", "/missing", "", "", "", 404},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			service := &stubService{}
			req := httptest.NewRequest(tt.method, tt.path, strings.NewReader(tt.body))
			if tt.auth != "" {
				req.Header.Set("Authorization", tt.auth)
			}
			if tt.contentType != "" {
				req.Header.Set("Content-Type", tt.contentType)
			}
			recorder := httptest.NewRecorder()
			httpapi.NewHandler(service).ServeHTTP(recorder, req)
			if recorder.Code != tt.status || service.calls != 0 {
				t.Fatalf("status=%d calls=%d body=%s", recorder.Code, service.calls, recorder.Body.String())
			}
			var body struct {
				Error struct{ Code, Message string }
			}
			if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil || body.Error.Code == "" || body.Error.Message == "" {
				t.Fatalf("invalid error body: %s", recorder.Body.String())
			}
		})
	}
}

func TestHTTPServiceErrors(t *testing.T) {
	tests := []struct {
		err    error
		status int
		code   string
	}{
		{chat.ErrUnauthorized, 401, "unauthorized"},
		{chat.ErrForbidden, 403, "wrong_room"},
		{chat.ErrRoomClosed, 409, "room_closed"},
		{chat.ErrCommandIDConflict, 409, "command_id_conflict"},
		{chat.ErrInvalidCommand, 422, "invalid_payload"},
		{chat.ErrRoomServiceUnavailable, 503, "room_service_unavailable"},
		{chat.ErrRoomServiceTimeout, 504, "room_service_timeout"},
		{chat.ErrStorageUnavailable, 503, "storage_unavailable"},
		{context.DeadlineExceeded, 504, "request_timeout"},
		{context.Canceled, 408, "request_cancelled"},
		{errors.New("internal secret"), 500, "internal_error"},
	}
	for _, tt := range tests {
		for _, method := range []string{"GET", "POST"} {
			t.Run(tt.code+"/"+method, func(t *testing.T) {
				service := &stubService{err: fmt.Errorf("secret-token: %w", tt.err)}
				path := "/rooms/r/messages"
				if method == "GET" {
					path += "/seq"
				}
				req := httptest.NewRequest(method, path, strings.NewReader(`{"command_id":"c","text":"hi"}`))
				req.Header.Set("Authorization", "Bearer token")
				req.Header.Set("Content-Type", "application/json")
				recorder := httptest.NewRecorder()
				httpapi.NewHandler(service).ServeHTTP(recorder, req)
				if recorder.Code != tt.status || !strings.Contains(recorder.Body.String(), `"code":"`+tt.code+`"`) || strings.Contains(recorder.Body.String(), "secret") {
					t.Fatalf("unexpected error: status=%d, body=%s", recorder.Code, recorder.Body.String())
				}
			})
		}
	}
}

func TestHTTPHealthUnchanged(t *testing.T) {
	service := &stubService{}
	recorder := httptest.NewRecorder()
	httpapi.NewHandler(service).ServeHTTP(recorder, httptest.NewRequest("GET", "/health", nil))
	if recorder.Code != 200 || recorder.Body.String() != "i'm still standing\n" || service.calls != 0 {
		t.Fatalf("health changed: status=%d, body=%s", recorder.Code, recorder.Body.String())
	}
}

func TestChatPreviewIsAvailableWithoutRoomToken(t *testing.T) {
	service := &stubService{}
	for _, path := range []string{"/chat/", "/chat/chat-widget.js", "/chat/chat-client.js"} {
		recorder := httptest.NewRecorder()
		httpapi.NewHandler(service).ServeHTTP(recorder, httptest.NewRequest("GET", path, nil))
		if recorder.Code != 200 || service.calls != 0 {
			t.Fatalf("frontend path %s: status=%d calls=%d", path, recorder.Code, service.calls)
		}
	}
}
