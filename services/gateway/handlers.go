package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/segmentio/kafka-go"
)

// --- request/response types ---

type CrawlRequest struct {
	URLs        []string `json:"urls"`
	Material    string   `json:"material,omitempty"`
	SourceLabel string   `json:"source_label,omitempty"`
}

type crawlKafkaBody struct {
	JobID       string `json:"job_id"`
	URL         string `json:"url"`
	Material    string `json:"material,omitempty"`
	SourceLabel string `json:"source_label,omitempty"`
}

type CrawlResponse struct {
	JobID    string `json:"job_id"`
	Accepted int    `json:"accepted"`
}

type PageResult struct {
	ID              int        `json:"id"`
	URL             string     `json:"url"`
	Domain          string     `json:"domain"`
	Title           *string    `json:"title"`
	MetaDescription *string    `json:"meta_description"`
	Score           *float64   `json:"score"`
	CrawledAt       *time.Time `json:"crawled_at"`
	Material        *string    `json:"material,omitempty"`
	SourceLabel     *string    `json:"source_label,omitempty"`
	JobID           *string    `json:"job_id,omitempty"`
	Summary         *string    `json:"summary,omitempty"`
	Recommendation  *string    `json:"recommendation,omitempty"`
}

type StatusResponse struct {
	Kafka    string `json:"kafka"`
	Redis    string `json:"redis"`
	Postgres string `json:"postgres"`
}

// --- handlers ---

// GET /health — simple liveness check
func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}

// GET /api/status — check if dependencies are reachable
func handleStatus(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	status := StatusResponse{
		Kafka:    "ok",
		Redis:    "ok",
		Postgres: "ok",
	}

	// check postgres
	if err := db.PingContext(ctx); err != nil {
		status.Postgres = fmt.Sprintf("error: %v", err)
	}

	// check redis
	if err := rdb.Ping(ctx).Err(); err != nil {
		status.Redis = fmt.Sprintf("error: %v", err)
	}

	// kafka — try to fetch metadata to see if broker is reachable
	conn, err := kafka.Dial("tcp", kafkaWriter.Addr.String())
	if err != nil {
		status.Kafka = fmt.Sprintf("error: %v", err)
	} else {
		conn.Close()
	}

	writeJSON(w, http.StatusOK, status)
}

// POST /api/crawl — publish URLs to kafka for crawling
func handleCrawl(w http.ResponseWriter, r *http.Request) {
	var req CrawlRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json body"})
		return
	}
	if len(req.URLs) == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "urls list is empty"})
		return
	}

	jobID := uuid.New().String()

	// build kafka messages, one per URL
	messages := make([]kafka.Message, len(req.URLs))
	for i, u := range req.URLs {
		payload, err := json.Marshal(crawlKafkaBody{
			JobID:       jobID,
			URL:         u,
			Material:    req.Material,
			SourceLabel: req.SourceLabel,
		})
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "encode crawl job"})
			return
		}
		messages[i] = kafka.Message{
			Key:   []byte(jobID),
			Value: payload,
		}
	}

	// publish to kafka
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	if err := kafkaWriter.WriteMessages(ctx, messages...); err != nil {
		log.Printf("kafka write error: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to queue crawl jobs"})
		return
	}

	writeJSON(w, http.StatusAccepted, CrawlResponse{
		JobID:    jobID,
		Accepted: len(req.URLs),
	})
}

// GET /api/results — list results, optional ?domain= ?material= ?limit= filters
func handleResults(w http.ResponseWriter, r *http.Request) {
	domain := r.URL.Query().Get("domain")
	material := r.URL.Query().Get("material")
	limitStr := r.URL.Query().Get("limit")
	limit := 50 // default
	if limitStr != "" {
		if v, err := strconv.Atoi(limitStr); err == nil && v > 0 {
			limit = v
		}
	}

	// try redis cache first (v2: includes material filter + new columns)
	cacheKey := fmt.Sprintf("results:v2:%s:%s:%d", domain, material, limit)
	ctx := r.Context()
	if cached, err := rdb.Get(ctx, cacheKey).Bytes(); err == nil {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Cache", "HIT")
		w.Write(cached)
		return
	}

	// query postgres — v1 is scoped to legacy sentinel org_id=0 so v2 tenant data
	// is never exposed via the unauthenticated v1 endpoint.
	query := `
		SELECT p.id, p.url, p.domain, p.title, p.meta_description, p.score, p.crawled_at,
		       p.material, p.source_label, p.job_id,
		       ar.summary, ar.recommendation
		FROM pages p
		LEFT JOIN analysis_results ar ON ar.page_id = p.id
	`
	args := []interface{}{}
	argPos := 1
	where := []string{"p.org_id = 0"}
	if domain != "" {
		where = append(where, fmt.Sprintf("p.domain = $%d", argPos))
		args = append(args, domain)
		argPos++
	}
	if material != "" {
		where = append(where, fmt.Sprintf("p.material = $%d", argPos))
		args = append(args, material)
		argPos++
	}
	query += " WHERE " + strings.Join(where, " AND ")
	query += " ORDER BY p.crawled_at DESC"
	query += fmt.Sprintf(" LIMIT %d", limit)

	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		log.Printf("query error: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "query failed"})
		return
	}
	defer rows.Close()

	results := []PageResult{}
	for rows.Next() {
		var pr PageResult
		var mat, src, jid sql.NullString
		if err := rows.Scan(&pr.ID, &pr.URL, &pr.Domain, &pr.Title,
			&pr.MetaDescription, &pr.Score, &pr.CrawledAt,
			&mat, &src, &jid,
			&pr.Summary, &pr.Recommendation); err != nil {
			log.Printf("scan error: %v", err)
			continue
		}
		pr.Material = nullStringPtr(mat)
		pr.SourceLabel = nullStringPtr(src)
		pr.JobID = nullStringPtr(jid)
		results = append(results, pr)
	}

	// cache for 30 seconds
	data, _ := json.Marshal(results)
	rdb.Set(ctx, cacheKey, data, 30*time.Second)

	w.Header().Set("X-Cache", "MISS")
	writeJSON(w, http.StatusOK, results)
}

// GET /api/results/{id} — single result by page ID
func handleResultByID(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid id"})
		return
	}

	query := `
		SELECT p.id, p.url, p.domain, p.title, p.meta_description, p.score, p.crawled_at,
		       p.material, p.source_label, p.job_id,
		       ar.summary, ar.recommendation
		FROM pages p
		LEFT JOIN analysis_results ar ON ar.page_id = p.id
		WHERE p.id = $1 AND p.org_id = 0
	`
	var pr PageResult
	var mat, src, jid sql.NullString
	err = db.QueryRowContext(r.Context(), query, id).Scan(
		&pr.ID, &pr.URL, &pr.Domain, &pr.Title,
		&pr.MetaDescription, &pr.Score, &pr.CrawledAt,
		&mat, &src, &jid,
		&pr.Summary, &pr.Recommendation,
	)
	if err == nil {
		pr.Material = nullStringPtr(mat)
		pr.SourceLabel = nullStringPtr(src)
		pr.JobID = nullStringPtr(jid)
	}
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	if err != nil {
		log.Printf("query error: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "query failed"})
		return
	}

	writeJSON(w, http.StatusOK, pr)
}

// --- helpers ---

func nullStringPtr(ns sql.NullString) *string {
	if !ns.Valid {
		return nil
	}
	s := ns.String
	return &s
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
