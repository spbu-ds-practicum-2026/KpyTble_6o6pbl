package postgres

import (
	"context"
	"fmt"
)

// CheckReady verifies connectivity and the columns needed by message operations.
// LIMIT 0 checks the schema without reading or changing messages.
func (r *Repository) CheckReady(ctx context.Context) error {
	rows, err := r.pool.Query(ctx, `
		SELECT c.room_id, c.last_message_seq,
		       m.message_id, m.participant_id, m.message_seq, m.text, m.created_at,
		       k.command_id, k.original_text
		FROM chat_room_counters c
		LEFT JOIN chat_messages m ON m.room_id = c.room_id
		LEFT JOIN chat_commands k ON k.message_id = m.message_id
		LIMIT 0`)
	if err != nil {
		return fmt.Errorf("chat database is not ready (check connectivity and migrations): %w", err)
	}
	defer rows.Close()
	// Query can return cached column descriptions before receiving the final
	// server response. Drain it so connection errors are observed by Err().
	for rows.Next() {
	}
	return rows.Err()
}
