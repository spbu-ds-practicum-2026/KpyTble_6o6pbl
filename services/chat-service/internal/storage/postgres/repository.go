package postgres

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"plotina/chat-service/internal/chat"
)

type Repository struct {
	pool *pgxpool.Pool
}

var _ chat.MessageRepository = (*Repository)(nil)

func NewRepository(pool *pgxpool.Pool) *Repository {
	return &Repository{pool: pool}
}

func (r *Repository) CurrentSeq(ctx context.Context, roomID string) (int64, error) {
	var seq int64
	err := r.pool.QueryRow(ctx, `
		SELECT last_message_seq FROM chat_room_counters WHERE room_id = $1`, roomID).Scan(&seq)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, fmt.Errorf("read room counter: %w", err)
	}
	return seq, nil
}

func (r *Repository) Append(ctx context.Context, input chat.NewMessage) (chat.SendResult, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.ReadCommitted})
	if err != nil {
		return chat.SendResult{}, fmt.Errorf("begin message transaction: %w", err)
	}
	defer func() {
		cleanup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = tx.Rollback(cleanup)
	}()

	if _, err := tx.Exec(ctx, `
		INSERT INTO chat_room_counters (room_id) VALUES ($1)
		ON CONFLICT (room_id) DO NOTHING`, input.RoomID); err != nil {
		return chat.SendResult{}, fmt.Errorf("ensure room counter: %w", err)
	}
	var seq int64
	if err := tx.QueryRow(ctx, `
		SELECT last_message_seq FROM chat_room_counters
		WHERE room_id = $1 FOR UPDATE`, input.RoomID).Scan(&seq); err != nil {
		return chat.SendResult{}, fmt.Errorf("lock room counter: %w", err)
	}

	// All commands in this room take the same row lock before checking retries.
	// This also serializes concurrent copies across different service instances.
	var message chat.Message
	var originalText string
	err = tx.QueryRow(ctx, `
		SELECT c.original_text, m.message_id, m.room_id, m.participant_id,
		       m.message_seq, m.text, m.created_at
		FROM chat_commands c
		JOIN chat_messages m ON m.message_id = c.message_id
		WHERE c.room_id = $1 AND c.participant_id = $2 AND c.command_id = $3`,
		input.RoomID, input.ParticipantID, input.CommandID,
	).Scan(&originalText, &message.MessageID, &message.RoomID, &message.ParticipantID,
		&message.MessageSeq, &message.Text, &message.CreatedAt)
	if err == nil {
		if originalText != input.Text {
			return chat.SendResult{}, chat.ErrCommandIDConflict
		}
		if err := tx.Commit(ctx); err != nil {
			return chat.SendResult{}, fmt.Errorf("commit repeated command: %w", err)
		}
		message.CreatedAt = message.CreatedAt.UTC()
		return chat.SendResult{CommandID: input.CommandID, Duplicate: true, Message: message}, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return chat.SendResult{}, fmt.Errorf("find command result: %w", err)
	}

	if err := tx.QueryRow(ctx, `
		UPDATE chat_room_counters SET last_message_seq = last_message_seq + 1
		WHERE room_id = $1 RETURNING last_message_seq`, input.RoomID).Scan(&seq); err != nil {
		return chat.SendResult{}, fmt.Errorf("increment room counter: %w", err)
	}
	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		return chat.SendResult{}, fmt.Errorf("generate message ID: %w", err)
	}
	message = chat.Message{
		MessageID: hex.EncodeToString(id[:]), RoomID: input.RoomID,
		ParticipantID: input.ParticipantID, Text: input.Text, MessageSeq: seq,
		// PostgreSQL stores timestamps with microsecond precision. Truncate before
		// returning so a retry reads back the exact same timestamp.
		CreatedAt: time.Now().UTC().Truncate(time.Microsecond),
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO chat_messages (message_id, room_id, participant_id, message_seq, text, created_at)
		VALUES ($1, $2, $3, $4, $5, $6)`,
		message.MessageID, message.RoomID, message.ParticipantID, message.MessageSeq,
		message.Text, message.CreatedAt); err != nil {
		return chat.SendResult{}, fmt.Errorf("save message: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO chat_commands (room_id, participant_id, command_id, original_text, message_id)
		VALUES ($1, $2, $3, $4, $5)`,
		input.RoomID, input.ParticipantID, input.CommandID, input.Text, message.MessageID); err != nil {
		return chat.SendResult{}, fmt.Errorf("save command result: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return chat.SendResult{}, fmt.Errorf("commit message: %w", err)
	}
	return chat.SendResult{CommandID: input.CommandID, Message: message}, nil
}
