package main

import (
	"database/sql"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
)

type insight struct {
	ID        int64   `json:"id"`
	GoalID    *int64  `json:"goal_id"`
	Kind      string  `json:"kind"`
	Title     string  `json:"title"`
	BodyMD    string  `json:"body_md"`
	AIModel   *string `json:"ai_model"`
	CreatedAt string  `json:"created_at"`
}

type evidence struct {
	ID                 int64   `json:"id"`
	EvidenceKind       string  `json:"evidence_kind"`
	PageID             *int64  `json:"page_id,omitempty"`
	PageURL            *string `json:"page_url,omitempty"`
	PageTitle          *string `json:"page_title,omitempty"`
	CatalogIndicatorID *int64  `json:"catalog_indicator_id,omitempty"`
	TenantIndicatorID  *int64  `json:"tenant_indicator_id,omitempty"`
	IndicatorCode      *string `json:"indicator_code,omitempty"`
	ReadingTS          *string `json:"reading_ts,omitempty"`
	Weight             float64 `json:"weight"`
	Excerpt            *string `json:"excerpt,omitempty"`
}

type insightDetail struct {
	insight
	Evidence []evidence `json:"evidence"`
}

// POST /api/v2/insights — typically called by background services; here we expose it
// authenticated so the copilot service (and the test endpoint) can both write.
type createInsightReq struct {
	GoalID  *int64           `json:"goal_id"`
	Kind    string           `json:"kind"`
	Title   string           `json:"title"`
	BodyMD  string           `json:"body_md"`
	AIModel string           `json:"ai_model,omitempty"`
	Evidence []evidenceInput `json:"evidence"`
}

type evidenceInput struct {
	Kind               string  `json:"kind"`           // 'page' | 'catalog_indicator' | 'tenant_indicator'
	PageID             *int64  `json:"page_id,omitempty"`
	CatalogIndicatorID *int64  `json:"catalog_indicator_id,omitempty"`
	TenantIndicatorID  *int64  `json:"tenant_indicator_id,omitempty"`
	ReadingTS          *string `json:"reading_ts,omitempty"`
	Weight             float64 `json:"weight,omitempty"`
	Excerpt            string  `json:"excerpt,omitempty"`
}

func handleV2InsightCreate(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req createInsightReq
	if err := decodeJSON(r, &req); err != nil || req.Title == "" || req.BodyMD == "" || req.Kind == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "title, body_md, kind required"})
		return
	}

	var aiModel sql.NullString
	if req.AIModel != "" {
		aiModel = sql.NullString{String: req.AIModel, Valid: true}
	}
	var goalID sql.NullInt64
	if req.GoalID != nil {
		goalID = sql.NullInt64{Int64: *req.GoalID, Valid: true}
	}
	var insightID int64
	err := tx.QueryRowContext(r.Context(),
		`INSERT INTO insights (org_id, goal_id, kind, title, body_md, ai_model)
		 VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
		s.OrgID, goalID, req.Kind, req.Title, req.BodyMD, aiModel,
	).Scan(&insightID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}

	// Insert evidence rows.
	for _, ev := range req.Evidence {
		weight := ev.Weight
		if weight == 0 {
			weight = 1.0
		}
		var rts sql.NullString
		if ev.ReadingTS != nil {
			rts = sql.NullString{String: *ev.ReadingTS, Valid: true}
		}
		var excerpt sql.NullString
		if ev.Excerpt != "" {
			excerpt = sql.NullString{String: ev.Excerpt, Valid: true}
		}
		_, err := tx.ExecContext(r.Context(),
			`INSERT INTO insight_evidence
			    (org_id, insight_id, evidence_kind, page_id, catalog_indicator_id, tenant_indicator_id, reading_ts, weight, excerpt)
			 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
			s.OrgID, insightID, ev.Kind, ev.PageID, ev.CatalogIndicatorID, ev.TenantIndicatorID, rts, weight, excerpt,
		)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": errMsg(err)})
			return
		}
	}

	writeJSON(w, http.StatusOK, map[string]int64{"id": insightID})
}

func handleV2InsightsList(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	q := r.URL.Query()
	args := []interface{}{}
	where := ""
	if g := q.Get("goal_id"); g != "" {
		if gid, err := strconv.ParseInt(g, 10, 64); err == nil {
			where = " WHERE goal_id = $1"
			args = append(args, gid)
		}
	}
	limit := 50
	if v, err := strconv.Atoi(q.Get("limit")); err == nil && v > 0 && v <= 200 {
		limit = v
	}
	sqlText := `SELECT id, goal_id, kind, title, body_md, ai_model, created_at
		      FROM insights` + where + ` ORDER BY created_at DESC LIMIT ` + strconv.Itoa(limit)

	rows, err := tx.QueryContext(r.Context(), sqlText, args...)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []insight{}
	for rows.Next() {
		var i insight
		var gid sql.NullInt64
		var ai sql.NullString
		var ts sql.NullTime
		if err := rows.Scan(&i.ID, &gid, &i.Kind, &i.Title, &i.BodyMD, &ai, &ts); err != nil {
			continue
		}
		if gid.Valid {
			v := gid.Int64
			i.GoalID = &v
		}
		i.AIModel = nullStringPtr(ai)
		if ts.Valid {
			i.CreatedAt = ts.Time.UTC().Format("2006-01-02T15:04:05Z")
		}
		out = append(out, i)
	}
	writeJSON(w, http.StatusOK, out)
}

func handleV2InsightDetail(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid id"})
		return
	}

	var i insight
	var gid sql.NullInt64
	var ai sql.NullString
	var ts sql.NullTime
	err = tx.QueryRowContext(r.Context(),
		`SELECT id, goal_id, kind, title, body_md, ai_model, created_at FROM insights WHERE id = $1`, id,
	).Scan(&i.ID, &gid, &i.Kind, &i.Title, &i.BodyMD, &ai, &ts)
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	if gid.Valid {
		v := gid.Int64
		i.GoalID = &v
	}
	i.AIModel = nullStringPtr(ai)
	if ts.Valid {
		i.CreatedAt = ts.Time.UTC().Format("2006-01-02T15:04:05Z")
	}

	// Evidence rows joined to page and catalog indicator for display.
	rows, err := tx.QueryContext(r.Context(), `
		SELECT ie.id, ie.evidence_kind, ie.page_id, ie.catalog_indicator_id, ie.tenant_indicator_id,
		       ie.reading_ts, ie.weight, ie.excerpt,
		       p.url, p.title,
		       COALESCE(cit.code, ti.code) AS indicator_code
		  FROM insight_evidence ie
		  LEFT JOIN pages p ON ie.evidence_kind = 'page' AND p.id = ie.page_id
		  LEFT JOIN catalog_indicator_template cit ON ie.evidence_kind = 'catalog_indicator' AND cit.id = ie.catalog_indicator_id
		  LEFT JOIN tenant_indicator ti ON ie.evidence_kind = 'tenant_indicator' AND ti.id = ie.tenant_indicator_id
		 WHERE ie.insight_id = $1
		 ORDER BY ie.created_at`, id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	evList := []evidence{}
	for rows.Next() {
		var ev evidence
		var pid, cid, tid sql.NullInt64
		var rts sql.NullTime
		var url, title, code, excerpt sql.NullString
		if err := rows.Scan(&ev.ID, &ev.EvidenceKind, &pid, &cid, &tid, &rts, &ev.Weight, &excerpt,
			&url, &title, &code); err != nil {
			continue
		}
		if pid.Valid {
			v := pid.Int64
			ev.PageID = &v
		}
		if cid.Valid {
			v := cid.Int64
			ev.CatalogIndicatorID = &v
		}
		if tid.Valid {
			v := tid.Int64
			ev.TenantIndicatorID = &v
		}
		if rts.Valid {
			s := rts.Time.UTC().Format("2006-01-02T15:04:05Z")
			ev.ReadingTS = &s
		}
		ev.PageURL = nullStringPtr(url)
		ev.PageTitle = nullStringPtr(title)
		ev.IndicatorCode = nullStringPtr(code)
		ev.Excerpt = nullStringPtr(excerpt)
		evList = append(evList, ev)
	}

	writeJSON(w, http.StatusOK, insightDetail{insight: i, Evidence: evList})
}

// GET /api/v2/me/briefing — most-recent briefing across goals; convenience wrapper.
func handleV2MeBriefing(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, goal_id, kind, title, body_md, ai_model, created_at
		   FROM insights
		  WHERE kind IN ('briefing','alert')
		  ORDER BY created_at DESC LIMIT 5`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []insight{}
	for rows.Next() {
		var i insight
		var gid sql.NullInt64
		var ai sql.NullString
		var ts sql.NullTime
		if err := rows.Scan(&i.ID, &gid, &i.Kind, &i.Title, &i.BodyMD, &ai, &ts); err != nil {
			continue
		}
		if gid.Valid {
			v := gid.Int64
			i.GoalID = &v
		}
		i.AIModel = nullStringPtr(ai)
		if ts.Valid {
			i.CreatedAt = ts.Time.UTC().Format("2006-01-02T15:04:05Z")
		}
		out = append(out, i)
	}
	writeJSON(w, http.StatusOK, out)
}
