package main

import (
	"database/sql"
	"fmt"

	"github.com/golang-migrate/migrate/v4"
	mpostgres "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

// runMigrations applies all up migrations from /app/migrations.
// Idempotent: skips already-applied versions tracked in schema_migrations.
func runMigrations(db *sql.DB, migrationsPath string) error {
	driver, err := mpostgres.WithInstance(db, &mpostgres.Config{})
	if err != nil {
		return fmt.Errorf("migrate driver: %w", err)
	}
	m, err := migrate.NewWithDatabaseInstance("file://"+migrationsPath, "postgres", driver)
	if err != nil {
		return fmt.Errorf("migrate init: %w", err)
	}
	if err := m.Up(); err != nil && err != migrate.ErrNoChange {
		return fmt.Errorf("migrate up: %w", err)
	}
	return nil
}
