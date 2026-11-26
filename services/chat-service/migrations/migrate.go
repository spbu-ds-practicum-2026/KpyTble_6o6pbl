// Package migrations applies embedded SQL migrations to the chat database.
package migrations

import (
	"context"
	"crypto/sha256"
	"embed"
	"errors"
	"fmt"
	"io/fs"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed *.up.sql
var files embed.FS

// Apply runs unapplied migrations in filename order in one transaction.
// Previously applied SQL must not be edited; add a new numbered file instead.
func Apply(ctx context.Context, pool *pgxpool.Pool) error {
	tx, err := pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.ReadCommitted})
	if err != nil {
		return fmt.Errorf("begin migrations: %w", err)
	}
	defer func() {
		cleanup, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = tx.Rollback(cleanup)
	}()

	// Serialize migration runners without depending on a table already existing.
	if _, err := tx.Exec(ctx, "SELECT pg_advisory_xact_lock(6767, 1)"); err != nil {
		return fmt.Errorf("lock migrations: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS chat_schema_migrations (
			name TEXT PRIMARY KEY,
			checksum TEXT NOT NULL,
			applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`); err != nil {
		return fmt.Errorf("create migration history: %w", err)
	}
	names, err := fs.Glob(files, "*.up.sql")
	if err != nil {
		return err
	}
	for _, name := range names {
		sql, err := files.ReadFile(name)
		if err != nil {
			return err
		}
		checksum := fmt.Sprintf("%x", sha256.Sum256(sql))
		var savedChecksum string
		err = tx.QueryRow(ctx, "SELECT checksum FROM chat_schema_migrations WHERE name = $1", name).Scan(&savedChecksum)
		if err == nil {
			if savedChecksum != checksum {
				return fmt.Errorf("applied migration %s was modified", name)
			}
			continue
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return fmt.Errorf("read migration %s: %w", name, err)
		}
		if _, err := tx.Exec(ctx, string(sql)); err != nil {
			return fmt.Errorf("apply migration %s: %w", name, err)
		}
		if _, err := tx.Exec(ctx, "INSERT INTO chat_schema_migrations (name, checksum) VALUES ($1, $2)", name, checksum); err != nil {
			return fmt.Errorf("record migration %s: %w", name, err)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("commit migrations: %w", err)
	}
	return nil
}
