package chat_test

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage"
)

func newService() *chat.Service {
	checker := rooms.NewFakeMembershipChecker(map[string]chat.Membership{
		"token-1": {RoomID: "room-1", UserID: "user-1"},
		"token-2": {RoomID: "room-1", UserID: "user-2"},
		"token-3": {RoomID: "room-2", UserID: "user-3"},
	})
	return chat.NewService(checker, storage.NewMemoryRepository())
}

func command() chat.SendCommand {
	return chat.SendCommand{
		RoomID: "room-1", UserID: "user-1", SessionToken: "token-1",
		CommandID: "command-1", Text: "Привет!",
	}
}

func TestSendMessage(t *testing.T) {
	result, err := newService().SendMessage(context.Background(), command())
	if err != nil {
		t.Fatal(err)
	}
	message := result.Message
	t.Logf("Собщение: %+v", message)
	if result.CommandID != "command-1" || result.Duplicate {
		t.Fatalf("unexpected result: %+v", result)
	}
	if message.MessageID == "" || message.RoomID != "room-1" || message.UserID != "user-1" ||
		message.Text != "Привет!" || message.MessageSeq != 1 || message.SentAt.IsZero() ||
		message.SentAt.Location() != time.UTC {
		t.Fatalf("unexpected message: %+v", message)
	}
}

func TestRejectedCommandsDoNotConsumeSequence(t *testing.T) {
	tests := []struct {
		name   string
		change func(*chat.SendCommand)
		want   error
	}{
		{"empty text", func(c *chat.SendCommand) { c.Text = " \n\t" }, chat.ErrInvalidCommand},
		{"empty command ID", func(c *chat.SendCommand) { c.CommandID = "" }, chat.ErrInvalidCommand},
		{"empty room", func(c *chat.SendCommand) { c.RoomID = "" }, chat.ErrInvalidCommand},
		{"empty user", func(c *chat.SendCommand) { c.UserID = "" }, chat.ErrInvalidCommand},
		{"empty token", func(c *chat.SendCommand) { c.SessionToken = "" }, chat.ErrUnauthorized},
		{"unknown token", func(c *chat.SendCommand) { c.SessionToken = "unknown" }, chat.ErrUnauthorized},
		{"wrong room", func(c *chat.SendCommand) { c.RoomID = "room-2" }, chat.ErrForbidden},
		{"wrong user", func(c *chat.SendCommand) { c.UserID = "user-2" }, chat.ErrForbidden},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			service := newService()
			input := command()
			tt.change(&input)
			if _, err := service.SendMessage(context.Background(), input); !errors.Is(err, tt.want) {
				t.Fatalf("got %v, want %v", err, tt.want)
			}
			result, err := service.SendMessage(context.Background(), command())
			if err != nil || result.Message.MessageSeq != 1 {
				t.Fatalf("rejected command changed storage: result=%+v, err=%v", result, err)
			}
		})
	}
}

func TestRetryReturnsOriginalMessage(t *testing.T) {
	service := newService()
	first, err := service.SendMessage(context.Background(), command())
	if err != nil {
		t.Fatal(err)
	}
	retry, err := service.SendMessage(context.Background(), command())
	if err != nil {
		t.Fatal(err)
	}
	if !retry.Duplicate || retry.Message != first.Message {
		t.Fatalf("retry must return the original message: %+v", retry)
	}
	input := command()
	input.CommandID = "command-2"
	next, err := service.SendMessage(context.Background(), input)
	if err != nil || next.Message.MessageSeq != 2 {
		t.Fatalf("retry consumed a sequence number: result=%+v, err=%v", next, err)
	}
}

func TestCommandIDConflict(t *testing.T) {
	service := newService()
	if _, err := service.SendMessage(context.Background(), command()); err != nil {
		t.Fatal(err)
	}
	input := command()
	input.Text = "Другой текст"
	if _, err := service.SendMessage(context.Background(), input); !errors.Is(err, chat.ErrCommandIDConflict) {
		t.Fatalf("got %v, want command ID conflict", err)
	}
	input.CommandID = "command-2"
	result, err := service.SendMessage(context.Background(), input)
	if err != nil || result.Message.MessageSeq != 2 {
		t.Fatalf("conflict consumed a sequence number: result=%+v, err=%v", result, err)
	}
}

func TestSequenceIsSharedByRoomAndCommandIDsAreScoped(t *testing.T) {
	service := newService()
	inputs := []chat.SendCommand{
		command(),
		{RoomID: "room-1", UserID: "user-2", SessionToken: "token-2", CommandID: "command-1", Text: "Второй участник"},
		{RoomID: "room-2", UserID: "user-3", SessionToken: "token-3", CommandID: "command-1", Text: "Другая комната"},
	}
	for i, input := range inputs {
		result, err := service.SendMessage(context.Background(), input)
		if err != nil {
			t.Fatal(err)
		}
		want := []int64{1, 2, 1}[i]
		if result.Duplicate || result.Message.MessageSeq != want {
			t.Fatalf("input %d: result=%+v, want sequence %d", i, result, want)
		}
	}
}

func TestConcurrentRetriesCreateOneMessage(t *testing.T) {
	service := newService()
	const count = 32
	results := make([]chat.SendResult, count)
	errs := make([]error, count)
	var wg sync.WaitGroup
	for i := range results {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			results[i], errs[i] = service.SendMessage(context.Background(), command())
		}(i)
	}
	wg.Wait()

	created := 0
	for i, result := range results {
		if errs[i] != nil {
			t.Fatal(errs[i])
		}
		if !result.Duplicate {
			created++
		}
		if result.Message != results[0].Message || result.Message.MessageSeq != 1 {
			t.Fatalf("concurrent retry created another message: %+v", result)
		}
	}
	if created != 1 {
		t.Fatalf("created %d messages, want 1", created)
	}
}

func TestCancelledContextDoesNotSaveMessage(t *testing.T) {
	service := newService()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := service.SendMessage(ctx, command()); !errors.Is(err, context.Canceled) {
		t.Fatalf("got %v, want context canceled", err)
	}
	result, err := service.SendMessage(context.Background(), command())
	if err != nil || result.Message.MessageSeq != 1 {
		t.Fatalf("cancelled command changed storage: result=%+v, err=%v", result, err)
	}
}

func TestConcurrentMessagesGetContinuousSequence(t *testing.T) {
	service := newService()
	const count = 32
	results := make([]chat.SendResult, count)
	errs := make([]error, count)
	var wg sync.WaitGroup
	for i := range results {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			input := command()
			input.CommandID = fmt.Sprintf("command-%d", i)
			results[i], errs[i] = service.SendMessage(context.Background(), input)
		}(i)
	}
	wg.Wait()

	sequences := make(map[int64]bool, count)
	messageIDs := make(map[string]bool, count)
	for i, result := range results {
		if errs[i] != nil {
			t.Fatal(errs[i])
		}
		message := result.Message
		if result.Duplicate || sequences[message.MessageSeq] || messageIDs[message.MessageID] {
			t.Fatalf("different commands must create unique messages: %+v", result)
		}
		sequences[message.MessageSeq] = true
		messageIDs[message.MessageID] = true
	}
	for seq := int64(1); seq <= count; seq++ {
		if !sequences[seq] {
			t.Fatalf("missing sequence number %d", seq)
		}
	}
}
