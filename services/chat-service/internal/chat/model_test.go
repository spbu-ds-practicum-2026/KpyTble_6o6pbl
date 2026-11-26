package chat_test

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"plotina/chat-service/internal/chat"
)

func TestSendCommandJSONContainsOnlyCommandAndText(t *testing.T) {
	data, err := json.Marshal(command())
	if err != nil {
		t.Fatal(err)
	}
	var fields map[string]any
	if err := json.Unmarshal(data, &fields); err != nil {
		t.Fatal(err)
	}
	want := map[string]any{"command_id": "command-1", "text": "Привет!"}
	if !reflect.DeepEqual(fields, want) {
		t.Fatalf("unexpected request body: %s", data)
	}
}

func TestSendCommandJSONCannotSetSessionOrAuthor(t *testing.T) {
	input := chat.SendCommand{RoomID: "room-1", SessionToken: "trusted-token"}
	data := []byte(`{"command_id":"cmd-1","text":"Привет","room_id":"other-room","SessionToken":"other-token","participant_id":"other-participant","user_id":"other-user"}`)
	if err := json.Unmarshal(data, &input); err != nil {
		t.Fatal(err)
	}
	want := chat.SendCommand{RoomID: "room-1", SessionToken: "trusted-token", CommandID: "cmd-1", Text: "Привет"}
	if input != want {
		t.Fatalf("body must not override URL, token or author: %+v", input)
	}
}

func TestSendResultJSONMatchesContract(t *testing.T) {
	result := chat.SendResult{
		CommandID: "cmd-7",
		Message: chat.Message{
			MessageID: "message-1", RoomID: "room-1", ParticipantID: "participant-1",
			Text: "Привет!", MessageSeq: 43,
			CreatedAt: time.Date(2026, time.November, 19, 12, 0, 0, 0, time.UTC),
		},
	}
	data, err := json.Marshal(result)
	if err != nil {
		t.Fatal(err)
	}
	var got map[string]any
	if err := json.Unmarshal(data, &got); err != nil {
		t.Fatal(err)
	}
	want := map[string]any{
		"command_id": "cmd-7", "duplicate": false,
		"message": map[string]any{
			"message_id": "message-1", "messageSeq": float64(43),
			"participant_id": "participant-1", "text": "Привет!",
			"created_at": "2026-11-19T12:00:00Z",
		},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("unexpected response body: %s", data)
	}
}

func TestMembershipJSONMatchesRoomService(t *testing.T) {
	data := []byte(`{"room_id":"room-1","participant_id":"participant-1","display_name":"Alice","role":"host","connected":true}`)
	var membership chat.Membership
	if err := json.Unmarshal(data, &membership); err != nil {
		t.Fatal(err)
	}
	want := chat.Membership{
		RoomID: "room-1", ParticipantID: "participant-1",
		DisplayName: "Alice", Role: chat.RoleHost, Connected: true,
	}
	if membership != want {
		t.Fatalf("got %+v, want %+v", membership, want)
	}
}
