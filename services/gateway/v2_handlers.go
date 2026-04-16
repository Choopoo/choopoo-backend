package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
)

// GET /api/v2/results — tenant-scoped read of crawled pages + insights.
// RLS guarantees rows from other orgs are invisible regardless of query shape.
func handleV2Results(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())

	domain := r.URL.Query().Get("domain")
	material := r.URL.Query().Get("material")
	limit := 50
	if v, err := strconv.Atoi(r.URL.Query().Get("limit")); err == nil && v > 0 && v <= 500 {
		limit = v
	}

	q := `
		SELECT p.id, p.url, p.domain, p.title, p.meta_description, p.score, p.crawled_at,
		       p.material, p.source_label, p.job_id, p.org_id,
		       ar.summary, ar.recommendation
		FROM pages p
		LEFT JOIN analysis_results ar ON ar.page_id = p.id
	`
	args := []interface{}{}
	pos := 1
	where := []string{}
	if domain != "" {
		where = append(where, fmt.Sprintf("p.domain = $%d", pos))
		args = append(args, domain)
		pos++
	}
	if material != "" {
		where = append(where, fmt.Sprintf("p.material = $%d", pos))
		args = append(args, material)
		pos++
	}
	if len(where) > 0 {
		q += " WHERE " + strings.Join(where, " AND ")
	}
	q += " ORDER BY p.crawled_at DESC NULLS LAST LIMIT " + strconv.Itoa(limit)

	rows, err := tx.QueryContext(r.Context(), q, args...)
	if err != nil {
		log.Printf("v2/results query: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "query"})
		return
	}
	defer rows.Close()

	type v2Row struct {
		ID              int64    `json:"id"`
		URL             string   `json:"url"`
		Domain          string   `json:"domain"`
		Title           *string  `json:"title"`
		MetaDescription *string  `json:"meta_description"`
		Score           *float64 `json:"score"`
		CrawledAt       *string  `json:"crawled_at"`
		Material        *string  `json:"material"`
		SourceLabel     *string  `json:"source_label"`
		JobID           *string  `json:"job_id"`
		OrgID           int64    `json:"org_id"`
		Summary         *string  `json:"summary"`
		Recommendation  *string  `json:"recommendation"`
	}

	out := []v2Row{}
	for rows.Next() {
		var row v2Row
		var crawled sql.NullTime
		var mat, src, jid, sum, rec sql.NullString
		if err := rows.Scan(
			&row.ID, &row.URL, &row.Domain, &row.Title, &row.MetaDescription,
			&row.Score, &crawled, &mat, &src, &jid, &row.OrgID, &sum, &rec,
		); err != nil {
			log.Printf("v2/results scan: %v", err)
			continue
		}
		if crawled.Valid {
			s := crawled.Time.UTC().Format("2006-01-02T15:04:05Z")
			row.CrawledAt = &s
		}
		row.Material = nullStringPtr(mat)
		row.SourceLabel = nullStringPtr(src)
		row.JobID = nullStringPtr(jid)
		row.Summary = nullStringPtr(sum)
		row.Recommendation = nullStringPtr(rec)
		out = append(out, row)
	}

	writeJSON(w, http.StatusOK, out)
}

// POST /api/v2/test/seed — dev-only: insert a synthetic page row under the
// caller's org. Used by the cross-tenant integration test to populate two orgs
// without involving the full kafka pipeline. Gated on ENABLE_TEST_ENDPOINTS=1.
//
// Body: { "url": "...", "title": "..." }
func handleV2TestSeed(w http.ResponseWriter, r *http.Request) {
	if getEnv("ENABLE_TEST_ENDPOINTS", "") != "1" {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())

	var body struct {
		URL   string `json:"url"`
		Title string `json:"title"`
	}
	if err := decodeJSON(r, &body); err != nil || body.URL == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "url required"})
		return
	}

	var id int64
	err := tx.QueryRowContext(r.Context(),
		`INSERT INTO pages (url, domain, title, score, material, source_label, org_id)
		 VALUES ($1, $2, $3, 1.0, 'TEST', 'seed', $4)
		 ON CONFLICT (url) DO UPDATE SET org_id = EXCLUDED.org_id, title = EXCLUDED.title
		 RETURNING id`,
		body.URL, "seed.local", body.Title, s.OrgID,
	).Scan(&id)
	if err != nil {
		log.Printf("v2/test/seed insert: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"id": id, "org_id": s.OrgID})
}

func decodeJSON(r *http.Request, v interface{}) error {
	defer r.Body.Close()
	return jsonDecode(r.Body, v)
}
