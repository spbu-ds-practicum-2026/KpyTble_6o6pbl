package rooms_test

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage"
)

func TestHTTPClientMembership(t *testing.T) {
	for _, connected := range []bool{true, false} {
		t.Run(fmt.Sprintf("connected=%t", connected), func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodGet || r.URL.Path != "/api/internal/rooms/room-1/membership" {
					t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
				}
				if r.Header.Get("Authorization") != "Bearer test-token" || r.URL.RawQuery != "" {
					t.Error("token must be sent only in the Authorization header")
				}
				if r.Header.Get("Accept") != "application/json" {
					t.Error("missing JSON Accept header")
				}
				w.Header().Set("Content-Type", "application/json")
				fmt.Fprintf(w, `{"room_id":"room-1","participant_id":"participant-1","display_name":"Alice","role":"host","connected":%t}`, connected)
			}))
			defer server.Close()
			client, err := rooms.NewHTTPClient(server.URL+"/api/", time.Second)
			if err != nil {
				t.Fatal(err)
			}
			got, err := client.CheckMembership(context.Background(), "room-1", "test-token")
			if err != nil {
				t.Fatal(err)
			}
			want := chat.Membership{RoomID: "room-1", ParticipantID: "participant-1", DisplayName: "Alice", Role: chat.RoleHost, Connected: connected}
			if got != want {
				t.Fatalf("got %+v, want %+v", got, want)
			}
		})
	}
}

func TestHTTPClientErrorResponses(t *testing.T) {
	tests := []struct {
		name   string
		status int
		body   string
		want   error
	}{
		{"unauthorized", 401, `{"error":{"code":"unauthorized","message":"secret-token"}}`, chat.ErrUnauthorized},
		{"wrong room", 403, `{"error":{"code":"wrong_room","message":"secret-token"}}`, chat.ErrForbidden},
		{"closed room", 409, `{"error":{"code":"room_closed","message":"secret-token"}}`, chat.ErrRoomClosed},
		{"server failure", 500, "secret-token", chat.ErrRoomServiceUnavailable},
		{"unrecognized status", 404, `{"error":{"code":"room_not_found"}}`, chat.ErrRoomServiceUnavailable},
		{"unrecognized error", 403, `{"error":{"code":"unknown","message":"secret-token"}}`, chat.ErrRoomServiceUnavailable},
		{"wrong status for code", 409, `{"error":{"code":"unauthorized"}}`, chat.ErrRoomServiceUnavailable},
		{"malformed error", 401, "secret-token", chat.ErrRoomServiceUnavailable},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
				w.WriteHeader(tt.status)
				_, _ = fmt.Fprint(w, tt.body)
			}))
			defer server.Close()
			client, err := rooms.NewHTTPClient(server.URL, time.Second)
			if err != nil {
				t.Fatal(err)
			}
			membership, err := client.CheckMembership(context.Background(), "room-1", "secret-token")
			if !errors.Is(err, tt.want) || membership != (chat.Membership{}) {
				t.Fatalf("got membership=%+v, err=%v, want %v", membership, err, tt.want)
			}
			if strings.Contains(err.Error(), "secret-token") {
				t.Fatal("error leaked the session token")
			}
		})
	}
}

func TestHTTPClientRejectsInvalidMembership(t *testing.T) {
	for _, body := range []string{
		`not JSON`,
		`null`,
		`{}`,
		`{"room_id":"another-room","participant_id":"p1","role":"host","connected":true}`,
		`{"room_id":"room-1","participant_id":" ","role":"host","connected":true}`,
		`{"room_id":"room-1","participant_id":"p1","role":"admin","connected":true}`,
		`{"room_id":"room-1","participant_id":"p1","role":"member"}`,
		`{"room_id":"room-1","participant_id":"p1","role":"member","connected":"yes"}`,
		strings.Repeat("x", 64*1024+1),
	} {
		t.Run(fmt.Sprintf("response-%d", len(body))+"-"+body[:min(12, len(body))], func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
				_, _ = fmt.Fprint(w, body)
			}))
			defer server.Close()
			client, err := rooms.NewHTTPClient(server.URL, time.Second)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := client.CheckMembership(context.Background(), "room-1", "token"); !errors.Is(err, chat.ErrRoomServiceUnavailable) {
				t.Fatalf("got %v, want invalid upstream response", err)
			}
		})
	}
}

func TestHTTPClientTimeoutIncludesResponseBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.(http.Flusher).Flush()
		<-r.Context().Done()
	}))
	defer server.Close()
	client, err := rooms.NewHTTPClient(server.URL, 100*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	_, err = client.CheckMembership(context.Background(), "room-1", "token")
	if !errors.Is(err, chat.ErrRoomServiceTimeout) || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("got %v, want Room Service timeout", err)
	}
}

func TestHTTPClientDoesNotFollowRedirects(t *testing.T) {
	destination := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		t.Error("redirect must not forward the membership request")
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer destination.Close()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, destination.URL, http.StatusTemporaryRedirect)
	}))
	defer server.Close()
	client, err := rooms.NewHTTPClient(server.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.CheckMembership(context.Background(), "room-1", "token"); !errors.Is(err, chat.ErrRoomServiceUnavailable) {
		t.Fatalf("got %v, want rejected redirect", err)
	}
}

func TestHTTPClientInvalidArgumentsDoNotSendRequests(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, _ *http.Request) {
		t.Error("invalid arguments must not cause a request")
	}))
	defer server.Close()
	client, err := rooms.NewHTTPClient(server.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	for _, token := range []string{"", " ", "token\r\nInjected: yes"} {
		if _, err := client.CheckMembership(context.Background(), "room-1", token); !errors.Is(err, chat.ErrUnauthorized) {
			t.Fatalf("got %v, want unauthorized", err)
		}
	}
	for _, roomID := range []string{"", " ", ".", "..", "../other", "room?token=x"} {
		if _, err := client.CheckMembership(context.Background(), roomID, "token"); !errors.Is(err, chat.ErrInvalidCommand) {
			t.Fatalf("got %v, want invalid command", err)
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := client.CheckMembership(ctx, "room-1", "token"); !errors.Is(err, context.Canceled) {
		t.Fatalf("got %v, want context canceled", err)
	}
}

func TestHTTPClientUnavailableServer(t *testing.T) {
	server := httptest.NewServer(http.NotFoundHandler())
	server.Close()
	client, err := rooms.NewHTTPClient(server.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.CheckMembership(context.Background(), "room-1", "token"); !errors.Is(err, chat.ErrRoomServiceUnavailable) {
		t.Fatalf("got %v, want unavailable", err)
	}
}

func TestHTTPClientConfiguration(t *testing.T) {
	for _, baseURL := range []string{"", "localhost:8000", "ftp://localhost", "http://", "http://user:secret@localhost", "http://localhost?token=secret", "http://localhost/#secret"} {
		if _, err := rooms.NewHTTPClient(baseURL, time.Second); err == nil {
			t.Fatalf("invalid base URL was accepted: %q", baseURL)
		} else if strings.Contains(err.Error(), "secret") {
			t.Fatal("configuration error must not echo credentials")
		}
	}
	for _, timeout := range []time.Duration{0, -time.Second} {
		if _, err := rooms.NewHTTPClient("http://localhost:8000", timeout); err == nil {
			t.Fatal("nonpositive timeout was accepted")
		}
	}
}

func TestChatServiceUsesHTTPMembership(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer valid-token" {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = fmt.Fprint(w, `{"error":{"code":"unauthorized","message":"Invalid session"}}`)
			return
		}
		_, _ = fmt.Fprint(w, `{"room_id":"room-1","participant_id":"real-participant","display_name":"Bob","role":"member","connected":true}`)
	}))
	defer server.Close()
	client, err := rooms.NewHTTPClient(server.URL, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	service := chat.NewService(client, storage.NewMemoryRepository())
	command := chat.SendCommand{RoomID: "room-1", SessionToken: "invalid-token", CommandID: "cmd-1", Text: "Привет"}
	if _, err := service.SendMessage(context.Background(), command); !errors.Is(err, chat.ErrUnauthorized) {
		t.Fatalf("got %v, want unauthorized", err)
	}
	command.SessionToken = "valid-token"
	result, err := service.SendMessage(context.Background(), command)
	if err != nil {
		t.Fatal(err)
	}
	if result.Message.ParticipantID != "real-participant" || result.Message.MessageSeq != 1 {
		t.Fatalf("wrong author or rejected command was saved: %+v", result)
	}
	command.SessionToken = "invalid-token"
	if _, err := service.SendMessage(context.Background(), command); !errors.Is(err, chat.ErrUnauthorized) {
		t.Fatalf("retry must check the token again, got %v", err)
	}
}

func TestHTTPClientHealth(t *testing.T) {
	for _, test := range []struct {
		body   string
		status int
		valid  bool
	}{
		{`{"status":"ok"}`, 200, true},
		{`{"status":"down"}`, 200, false},
		{`not-json`, 200, false},
		{`{"status":"ok"}`, 503, false},
	} {
		t.Run(fmt.Sprintf("%d-%s", test.status, test.body), func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/api/health" || r.Header.Get("Authorization") != "" {
					t.Error("health must use /health without a session token")
				}
				w.WriteHeader(test.status)
				_, _ = fmt.Fprint(w, test.body)
			}))
			defer server.Close()
			client, err := rooms.NewHTTPClient(server.URL+"/api", time.Second)
			if err != nil {
				t.Fatal(err)
			}
			err = client.CheckHealth(context.Background())
			if (err == nil) != test.valid {
				t.Fatalf("health error=%v, want valid=%t", err, test.valid)
			}
		})
	}
}
