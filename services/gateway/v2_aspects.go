package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
)

type aspect struct {
	ID               int64   `json:"id"`
	Code             string  `json:"code"`
	Name             string  `json:"name"`
	Description      *string `json:"description"`
	Axis             string  `json:"axis"`
	DefaultRelevance float64 `json:"default_relevance"`
}

type subjectAspectRow struct {
	SubjectCode         string           `json:"subject_code"`
	AspectID            int64            `json:"aspect_id"`
	AspectCode          string           `json:"aspect_code"`
	AspectName          string           `json:"aspect_name"`
	Axis                string           `json:"axis"`
	Status              string           `json:"status"`
	RelevanceR          *float64         `json:"relevance_r"`
	DiversityBonus      *float64         `json:"diversity_bonus"`
	Score               *float64         `json:"score"`
	RelevanceRationale  *string          `json:"relevance_rationale"`
	InductionChain      json.RawMessage  `json:"induction_chain"`
	ExampleEvents       json.RawMessage  `json:"example_events"`
	EvidenceVerified    bool             `json:"evidence_verified"`
	LastScoredAt        *string          `json:"last_scored_at"`
	ProviderCount       int              `json:"provider_count"`
}

// GET /api/v2/aspects — full catalog of signal aspects.
func handleV2AspectsList(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, code, name, description, axis, default_relevance
		   FROM catalog_signal_aspect ORDER BY default_relevance DESC, code`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []aspect{}
	for rows.Next() {
		var a aspect
		var desc sql.NullString
		if err := rows.Scan(&a.ID, &a.Code, &a.Name, &desc, &a.Axis, &a.DefaultRelevance); err != nil {
			continue
		}
		a.Description = nullStringPtr(desc)
		out = append(out, a)
	}
	writeJSON(w, http.StatusOK, out)
}

// GET /api/v2/subjects/:code/aspects?status=active|candidate|rejected|all
func handleV2SubjectAspects(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	code := chi.URLParam(r, "code")
	status := r.URL.Query().Get("status")
	if status == "" {
		status = "all"
	}

	args := []interface{}{code}
	where := "sas.subject_code = $1"
	if status != "all" {
		where += " AND sas.status = $2"
		args = append(args, status)
	}

	q := `
		SELECT sas.subject_code, sas.aspect_id, csa.code, csa.name, csa.axis, sas.status,
		       sas.relevance_r, sas.diversity_bonus, sas.score,
		       sas.relevance_rationale,
		       COALESCE(sas.induction_chain, 'null'::jsonb),
		       COALESCE(sas.example_events, '[]'::jsonb),
		       sas.evidence_verified, sas.last_scored_at,
		       (SELECT COUNT(*) FROM aspect_provider ap WHERE ap.aspect_id = sas.aspect_id) AS provider_count
		  FROM subject_aspect_score sas
		  JOIN catalog_signal_aspect csa ON csa.id = sas.aspect_id
		 WHERE ` + where + `
		 ORDER BY sas.score DESC NULLS LAST`

	rows, err := tx.QueryContext(r.Context(), q, args...)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []subjectAspectRow{}
	for rows.Next() {
		var row subjectAspectRow
		var rationale sql.NullString
		var chainStr, exStr sql.NullString
		var ts sql.NullTime
		var relR, divB, score sql.NullFloat64
		if err := rows.Scan(&row.SubjectCode, &row.AspectID, &row.AspectCode, &row.AspectName, &row.Axis, &row.Status,
			&relR, &divB, &score,
			&rationale, &chainStr, &exStr,
			&row.EvidenceVerified, &ts, &row.ProviderCount); err != nil {
			continue
		}
		if relR.Valid { v := relR.Float64; row.RelevanceR = &v }
		if divB.Valid { v := divB.Float64; row.DiversityBonus = &v }
		if score.Valid { v := score.Float64; row.Score = &v }
		row.RelevanceRationale = nullStringPtr(rationale)
		if chainStr.Valid { row.InductionChain = json.RawMessage(chainStr.String) } else { row.InductionChain = json.RawMessage("null") }
		if exStr.Valid { row.ExampleEvents = json.RawMessage(exStr.String) } else { row.ExampleEvents = json.RawMessage("[]") }
		if ts.Valid {
			s := ts.Time.UTC().Format("2006-01-02T15:04:05Z")
			row.LastScoredAt = &s
		}
		out = append(out, row)
	}
	writeJSON(w, http.StatusOK, out)
}

// POST /api/v2/subjects/:code/aspects/:aspectId  body: {"active": bool}
// Toggles an aspect between active and candidate.
func handleV2ToggleSubjectAspect(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	code := chi.URLParam(r, "code")
	aspectID, err := strconv.ParseInt(chi.URLParam(r, "aspectId"), 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid aspect id"})
		return
	}
	var body struct {
		Active bool `json:"active"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "body required"})
		return
	}
	status := "candidate"
	if body.Active {
		status = "active"
	}
	res, err := tx.ExecContext(r.Context(),
		`UPDATE subject_aspect_score SET status = $1 WHERE subject_code = $2 AND aspect_id = $3`,
		status, code, aspectID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "subject/aspect pair not found"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": status})
}
