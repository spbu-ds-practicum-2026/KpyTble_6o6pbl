package storage

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"

	"plotina/chat-service/internal/chat"
)

// MemoryRepository is temporary storage for local development and tests.
// Data is lost on restart; the mutex coordinates only this instance.
type MemoryRepository struct {
	mu        sync.Mutex
	sequences map[string]int64
	commands  map[commandKey]chat.Message
}

type commandKey struct {
	roomID        string
	participantID string
	commandID     string
}

func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{
		sequences: make(map[string]int64),
		commands:  make(map[commandKey]chat.Message),
	}
}

func (r *MemoryRepository) CurrentSeq(ctx context.Context, roomID string) (int64, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return 0, err
	}
	return r.sequences[roomID], nil
}

func (r *MemoryRepository) Append(ctx context.Context, input chat.NewMessage) (chat.SendResult, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if err := ctx.Err(); err != nil {
		return chat.SendResult{}, err
	}

	key := commandKey{roomID: input.RoomID, participantID: input.ParticipantID, commandID: input.CommandID}
	if message, ok := r.commands[key]; ok {
		if message.Text != input.Text {
			return chat.SendResult{}, chat.ErrCommandIDConflict
		}
		return chat.SendResult{CommandID: input.CommandID, Duplicate: true, Message: message}, nil
	}

	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		return chat.SendResult{}, err
	}
	message := chat.Message{
		MessageID:     hex.EncodeToString(id[:]),
		RoomID:        input.RoomID,
		ParticipantID: input.ParticipantID,
		Text:          input.Text,
		CreatedAt:     time.Now().UTC(),
		MessageSeq:    r.sequences[input.RoomID] + 1,
	}
	r.sequences[input.RoomID] = message.MessageSeq
	r.commands[key] = message

	return chat.SendResult{CommandID: input.CommandID, Message: message}, nil
}
