package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

// publishDomainEvent inserts a row into the domain_events outbox table IN THE
// SAME TX as the triggering write. The relay goroutine will later drain unpublished
// rows to Kafka. This guarantees atomicity: if the commit rolls back, no event.
//
// Kind is a dotted namespace like "goal.created.v1"; payload is any JSON-able value.
func publishDomainEvent(ctx context.Context, tx *sql.Tx, orgID int64, kind string, payload interface{}) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx,
		`INSERT INTO domain_events (org_id, kind, payload) VALUES ($1, $2, $3::jsonb)`,
		orgID, kind, string(data),
	)
	return err
}

// startOutboxRelay begins a background goroutine that drains unpublished events
// from `domain_events` into their respective Kafka topics. Kind-per-topic:
// "goal.created.v1" -> topic "goal.created.v1", etc.
//
// Uses pipeline (BYPASSRLS) connection to read across all orgs. At-least-once
// delivery: marks published AFTER Kafka returns success. Duplicate consumers
// must be idempotent (they are — workflow_runs is keyed by event_id + org_id).
func startOutboxRelay(ctx context.Context, db *sql.DB, brokers []string, interval time.Duration) {
	writer := &kafka.Writer{
		Addr:                   kafka.TCP(brokers...),
		Balancer:               &kafka.LeastBytes{},
		BatchTimeout:           5 * time.Millisecond,
		AllowAutoTopicCreation: true,
	}
	go func() {
		defer writer.Close()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				if err := drainOutbox(ctx, db, writer); err != nil {
					log.Printf("outbox relay: %v", err)
				}
			}
		}
	}()
	log.Printf("outbox relay started (interval=%s)", interval)
}

func drainOutbox(ctx context.Context, db *sql.DB, writer *kafka.Writer) error {
	rows, err := db.QueryContext(ctx,
		`SELECT id, org_id, kind, payload::text FROM domain_events
		  WHERE published_at IS NULL
		  ORDER BY id
		  LIMIT 100`)
	if err != nil {
		return err
	}
	type ev struct {
		id      int64
		orgID   int64
		kind    string
		payload string
	}
	evs := []ev{}
	for rows.Next() {
		var e ev
		if err := rows.Scan(&e.id, &e.orgID, &e.kind, &e.payload); err != nil {
			rows.Close()
			return err
		}
		evs = append(evs, e)
	}
	rows.Close()
	if len(evs) == 0 {
		return nil
	}

	for _, e := range evs {
		msg := kafka.Message{
			Topic: e.kind,
			Key:   []byte(itoa(e.orgID)),
			Value: []byte(e.payload),
			Headers: []kafka.Header{
				{Key: "X-Event-Id", Value: []byte(itoa(e.id))},
				{Key: "X-Org-Id", Value: []byte(itoa(e.orgID))},
				{Key: "X-Kind", Value: []byte(e.kind)},
			},
		}
		if err := writer.WriteMessages(ctx, msg); err != nil {
			return err
		}
		if _, err := db.ExecContext(ctx,
			`UPDATE domain_events SET published_at = NOW() WHERE id = $1`, e.id); err != nil {
			return err
		}
	}
	log.Printf("outbox: drained %d event(s)", len(evs))
	return nil
}

func itoa(n int64) string {
	// Avoid strconv import churn elsewhere; small helper.
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	buf := [20]byte{}
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}
