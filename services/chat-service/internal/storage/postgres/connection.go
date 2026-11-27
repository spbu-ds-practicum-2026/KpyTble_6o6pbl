// Package postgres implements persistent chat storage in its own PostgreSQL database.
package postgres

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Open validates the configuration and checks that the database is reachable.
// The caller owns the pool and must close it when it is no longer needed.
func Open(ctx context.Context, databaseURL string) (*pgxpool.Pool, error) {
	if strings.TrimSpace(databaseURL) == "" {
		return nil, errors.New("CHAT_DATABASE_URL is required")
	}
	config, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		// Parsing errors may contain credentials from the connection string.
		return nil, errors.New("invalid CHAT_DATABASE_URL")
	}
	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, errors.New("cannot create chat database pool: check CHAT_DATABASE_URL")
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, errors.New("cannot connect to chat database: check address, credentials and database availability")
	}
	return pool, nil
}
