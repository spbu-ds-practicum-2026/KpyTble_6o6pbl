package postgres_test

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/storage/postgres"
	"plotina/chat-service/migrations"
)

// Each integration test gets a separate schema. Existing application tables
// are not read or modified. The test role must be allowed to create schemas.
func setupDatabase(t *testing.T) (*pgxpool.Pool, func() *pgxpool.Pool) {
	t.Helper()
	databaseURL := os.Getenv("CHAT_TEST_DATABASE_URL")
	if databaseURL == "" {
		t.Skip("set CHAT_TEST_DATABASE_URL to run PostgreSQL integration tests")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	admin, err := postgres.Open(ctx, databaseURL)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(admin.Close)
	var id [8]byte
	if _, err := rand.Read(id[:]); err != nil {
		t.Fatal(err)
	}
	schema := "chat_test_" + hex.EncodeToString(id[:])
	quotedSchema := pgx.Identifier{schema}.Sanitize()
	if _, err := admin.Exec(ctx, "CREATE SCHEMA "+quotedSchema); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		if _, err := admin.Exec(ctx, "DROP SCHEMA "+quotedSchema+" CASCADE"); err != nil {
			t.Errorf("clean test schema: %v", err)
		}
	})
	newPool := func() *pgxpool.Pool {
		t.Helper()
		config, err := pgxpool.ParseConfig(databaseURL)
		if err != nil {
			t.Fatal("invalid CHAT_TEST_DATABASE_URL")
		}
		config.ConnConfig.RuntimeParams["search_path"] = schema
		config.MaxConns = 8
		pool, err := pgxpool.NewWithConfig(context.Background(), config)
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(pool.Close)
		return pool
	}
	pool := newPool()
	if err := postgres.NewRepository(pool).CheckReady(ctx); err == nil {
		t.Fatal("database without migrations must not be ready")
	}
	if err := migrations.Apply(ctx, pool); err != nil {
		t.Fatal(err)
	}
	if err := postgres.NewRepository(pool).CheckReady(ctx); err != nil {
		t.Fatalf("migrated database must be ready: %v", err)
	}
	return pool, newPool
}

func newMessage() chat.NewMessage {
	return chat.NewMessage{RoomID: "room-1", ParticipantID: "participant-1", CommandID: "command-1", Text: "Привет!"}
}

func TestPostgresMigrationsAreRepeatable(t *testing.T) {
	pool, _ := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := migrations.Apply(ctx, pool); err != nil {
		t.Fatal(err)
	}
	var count int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM chat_schema_migrations").Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("got %d migration records, want 1", count)
	}
	if _, err := pool.Exec(ctx, "UPDATE chat_schema_migrations SET checksum = 'changed'"); err != nil {
		t.Fatal(err)
	}
	if err := migrations.Apply(ctx, pool); err == nil {
		t.Fatal("modified migration checksum must be rejected")
	}
}

func TestPostgresRetryAndPersistence(t *testing.T) {
	pool, newPool := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	first, err := postgres.NewRepository(pool).Append(ctx, newMessage())
	if err != nil {
		t.Fatal(err)
	}
	if first.Duplicate || first.Message.MessageID == "" || first.Message.MessageSeq != 1 ||
		first.Message.CreatedAt.IsZero() || first.Message.CreatedAt.Location() != time.UTC {
		t.Fatalf("unexpected first message: %+v", first)
	}
	pool.Close()
	// A new connection pool and repository must see the persisted result.
	repository := postgres.NewRepository(newPool())
	retry, err := repository.Append(ctx, newMessage())
	if err != nil {
		t.Fatal(err)
	}
	if !retry.Duplicate || retry.Message != first.Message {
		t.Fatalf("retry changed persisted message: first=%+v, retry=%+v", first, retry)
	}
	input := newMessage()
	input.Text = "Другой текст"
	if _, err := repository.Append(ctx, input); !errors.Is(err, chat.ErrCommandIDConflict) {
		t.Fatalf("got %v, want command ID conflict", err)
	}
	input.CommandID = "command-2"
	next, err := repository.Append(ctx, input)
	if err != nil || next.Message.MessageSeq != 2 {
		t.Fatalf("retry or conflict consumed a sequence: result=%+v, err=%v", next, err)
	}
}

func TestPostgresDownMigration(t *testing.T) {
	pool, _ := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if _, err := postgres.NewRepository(pool).Append(ctx, newMessage()); err != nil {
		t.Fatal(err)
	}
	down, err := os.ReadFile("../../../migrations/001_init.down.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(down)); err != nil {
		t.Fatal(err)
	}
	for _, table := range []string{"chat_commands", "chat_messages", "chat_room_counters"} {
		var removed bool
		if err := pool.QueryRow(ctx, "SELECT to_regclass($1) IS NULL", table).Scan(&removed); err != nil {
			t.Fatal(err)
		}
		if !removed {
			t.Fatalf("down migration did not remove %s", table)
		}
	}
}

func TestPostgresRoomCountersAndParticipantScope(t *testing.T) {
	pool, _ := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	repository := postgres.NewRepository(pool)
	inputs := []chat.NewMessage{
		newMessage(),
		{RoomID: "room-1", ParticipantID: "participant-2", CommandID: "command-1", Text: "Другой участник"},
		{RoomID: "room-2", ParticipantID: "participant-3", CommandID: "command-1", Text: "Другая комната"},
	}
	for i, input := range inputs {
		result, err := repository.Append(ctx, input)
		if err != nil {
			t.Fatal(err)
		}
		if result.Duplicate || result.Message.MessageSeq != []int64{1, 2, 1}[i] {
			t.Fatalf("unexpected result for input %d: %+v", i, result)
		}
	}
}

func TestPostgresRollbackDoesNotConsumeSequence(t *testing.T) {
	pool, _ := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	repository := postgres.NewRepository(pool)
	input := newMessage()
	// Fail at the final command INSERT, after the counter and message INSERT.
	input.CommandID = ""
	if _, err := repository.Append(ctx, input); err == nil {
		t.Fatal("expected database constraint error")
	}
	for _, table := range []string{"chat_room_counters", "chat_messages", "chat_commands"} {
		var count int
		if err := pool.QueryRow(ctx, "SELECT count(*) FROM "+table).Scan(&count); err != nil {
			t.Fatal(err)
		}
		if count != 0 {
			t.Fatalf("rollback left %d rows in %s", count, table)
		}
	}
	first, err := repository.Append(ctx, newMessage())
	if err != nil || first.Message.MessageSeq != 1 {
		t.Fatalf("failed transaction consumed sequence 1: result=%+v, err=%v", first, err)
	}
	if _, err := repository.Append(ctx, input); err == nil {
		t.Fatal("expected another constraint error")
	}
	input.CommandID = "command-2"
	next, err := repository.Append(ctx, input)
	if err != nil || next.Message.MessageSeq != 2 {
		t.Fatalf("failed transaction consumed sequence 2: result=%+v, err=%v", next, err)
	}
}

func TestPostgresConcurrentWritesAcrossPools(t *testing.T) {
	for _, retries := range []bool{false, true} {
		t.Run(fmt.Sprintf("retries=%t", retries), func(t *testing.T) {
			pool, newPool := setupDatabase(t)
			repositories := []*postgres.Repository{postgres.NewRepository(pool), postgres.NewRepository(newPool())}
			ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
			defer cancel()
			const count = 32
			results := make([]chat.SendResult, count)
			errs := make([]error, count)
			var wg sync.WaitGroup
			for i := range results {
				wg.Add(1)
				go func(i int) {
					defer wg.Done()
					input := newMessage()
					if !retries {
						input.CommandID = fmt.Sprintf("command-%d", i)
					}
					results[i], errs[i] = repositories[i%len(repositories)].Append(ctx, input)
				}(i)
			}
			wg.Wait()
			seen := make(map[int64]bool)
			created := 0
			for i, result := range results {
				if errs[i] != nil {
					t.Fatal(errs[i])
				}
				if !result.Duplicate {
					created++
				}
				if retries {
					if result.Message != results[0].Message {
						t.Fatalf("retry changed message: %+v", result)
					}
				} else if seen[result.Message.MessageSeq] {
					t.Fatalf("duplicate sequence: %d", result.Message.MessageSeq)
				}
				seen[result.Message.MessageSeq] = true
			}
			want := count
			if retries {
				want = 1
			}
			if created != want {
				t.Fatalf("created %d messages, want %d", created, want)
			}
			for seq := int64(1); seq <= int64(want); seq++ {
				if !seen[seq] {
					t.Fatalf("missing sequence %d", seq)
				}
			}
			for _, table := range []string{"chat_messages", "chat_commands"} {
				var total int
				if err := pool.QueryRow(ctx, "SELECT count(*) FROM "+table).Scan(&total); err != nil {
					t.Fatal(err)
				}
				if total != want {
					t.Fatalf("got %d rows in %s, want %d", total, table, want)
				}
			}
		})
	}
}

func TestPostgresCancelledCommandDoesNotWrite(t *testing.T) {
	pool, _ := setupDatabase(t)
	repository := postgres.NewRepository(pool)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := repository.Append(ctx, newMessage()); !errors.Is(err, context.Canceled) {
		t.Fatalf("got %v, want context canceled", err)
	}
	ctx, cancel = context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	result, err := repository.Append(ctx, newMessage())
	if err != nil || result.Message.MessageSeq != 1 {
		t.Fatalf("cancelled command changed database: result=%+v, err=%v", result, err)
	}
}

func TestPostgresCurrentSeqIsReadOnly(t *testing.T) {
	pool, _ := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	repository := postgres.NewRepository(pool)
	seq, err := repository.CurrentSeq(ctx, "room-1")
	if err != nil || seq != 0 {
		t.Fatalf("empty room: seq=%d, err=%v", seq, err)
	}
	var counters int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM chat_room_counters").Scan(&counters); err != nil || counters != 0 {
		t.Fatalf("read created a counter: count=%d, err=%v", counters, err)
	}
	if _, err := repository.Append(ctx, newMessage()); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		seq, err := repository.CurrentSeq(ctx, "room-1")
		if err != nil || seq != 1 {
			t.Fatalf("read changed sequence: seq=%d, err=%v", seq, err)
		}
	}
	if seq, err := repository.CurrentSeq(ctx, "room-2"); err != nil || seq != 0 {
		t.Fatalf("room isolation failed: seq=%d, err=%v", seq, err)
	}
}

func TestPostgresReadinessAfterConnectionLoss(t *testing.T) {
	pool, newPool := setupDatabase(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	repository := postgres.NewRepository(pool)
	if err := repository.CheckReady(ctx); err != nil {
		t.Fatal(err)
	}
	var pid int32
	if err := pool.QueryRow(ctx, "SELECT pg_backend_pid()").Scan(&pid); err != nil {
		t.Fatal(err)
	}
	other := newPool()
	// Terminate an idle connection after its prepared statement was cached.
	// Only the exact connection opened by this test is affected.
	if _, err := other.Exec(ctx, "SELECT pg_terminate_backend($1)", pid); err != nil {
		t.Fatal(err)
	}
	// The pool may discard the dead connection and transparently open another.
	// If not, a subsequent check must recover without a process restart.
	_ = repository.CheckReady(ctx)
	if err := repository.CheckReady(ctx); err != nil {
		t.Fatalf("readiness did not recover: %v", err)
	}
	pool.Close()
	if err := repository.CheckReady(ctx); err == nil {
		t.Fatal("closed pool must not be ready")
	}
}
