package main

import (
	"database/sql"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
)

type goal struct {
	ID          int64   `json:"id"`
	UserID      *int64  `json:"user_id"`
	Title       string  `json:"title"`
	Lens        string  `json:"lens"`
	HorizonDays *int    `json:"horizon_days"`
	Pinned      bool    `json:"pinned"`
	Description *string `json:"description"`
	CreatedAt   string  `json:"created_at"`
}

type goalIndicatorLink struct {
	ID            int64  `json:"id"`
	IndicatorKind string `json:"indicator_kind"` // "catalog" | "tenant"
	IndicatorID   int64  `json:"indicator_id"`
	IndicatorCode string `json:"indicator_code"`
	Role          string `json:"role"`
}

type goalDetail struct {
	goal
	Indicators []goalIndicatorLink `json:"indicators"`
}

type createGoalReq struct {
	Title       string `json:"title"`
	Lens        string `json:"lens"`
	HorizonDays *int   `json:"horizon_days,omitempty"`
	Pinned      bool   `json:"pinned,omitempty"`
	Description string `json:"description,omitempty"`
}

func handleV2GoalsCreate(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	var req createGoalReq
	if err := decodeJSON(r, &req); err != nil || req.Title == "" || req.Lens == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "title and lens required"})
		return
	}
	if req.Lens != "buy" && req.Lens != "sell" && req.Lens != "macro" && req.Lens != "mixed" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "lens must be buy|sell|macro|mixed"})
		return
	}

	var (
		id      int64
		desc    sql.NullString
		horizon sql.NullInt64
	)
	if req.Description != "" {
		desc = sql.NullString{String: req.Description, Valid: true}
	}
	if req.HorizonDays != nil {
		horizon = sql.NullInt64{Int64: int64(*req.HorizonDays), Valid: true}
	}
	err := tx.QueryRowContext(r.Context(),
		`INSERT INTO goals (org_id, user_id, title, lens, horizon_days, pinned, description)
		 VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`,
		s.OrgID, s.UserID, req.Title, req.Lens, horizon, req.Pinned, desc,
	).Scan(&id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"id": id})
}

func handleV2GoalsList(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	rows, err := tx.QueryContext(r.Context(),
		`SELECT id, user_id, title, lens, horizon_days, pinned, description, created_at
		   FROM goals ORDER BY pinned DESC, created_at DESC`)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []goal{}
	for rows.Next() {
		var g goal
		var uid sql.NullInt64
		var horizon sql.NullInt64
		var desc sql.NullString
		var ts sql.NullTime
		if err := rows.Scan(&g.ID, &uid, &g.Title, &g.Lens, &horizon, &g.Pinned, &desc, &ts); err != nil {
			continue
		}
		if uid.Valid {
			v := uid.Int64
			g.UserID = &v
		}
		if horizon.Valid {
			v := int(horizon.Int64)
			g.HorizonDays = &v
		}
		g.Description = nullStringPtr(desc)
		if ts.Valid {
			g.CreatedAt = ts.Time.UTC().Format("2006-01-02T15:04:05Z")
		}
		out = append(out, g)
	}
	writeJSON(w, http.StatusOK, out)
}

func handleV2GoalDetail(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid id"})
		return
	}

	var g goal
	var uid sql.NullInt64
	var horizon sql.NullInt64
	var desc sql.NullString
	var ts sql.NullTime
	err = tx.QueryRowContext(r.Context(),
		`SELECT id, user_id, title, lens, horizon_days, pinned, description, created_at
		   FROM goals WHERE id = $1`, id,
	).Scan(&g.ID, &uid, &g.Title, &g.Lens, &horizon, &g.Pinned, &desc, &ts)
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	if uid.Valid {
		v := uid.Int64
		g.UserID = &v
	}
	if horizon.Valid {
		v := int(horizon.Int64)
		g.HorizonDays = &v
	}
	g.Description = nullStringPtr(desc)
	if ts.Valid {
		g.CreatedAt = ts.Time.UTC().Format("2006-01-02T15:04:05Z")
	}

	links, err := loadGoalLinks(r, tx, id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, goalDetail{goal: g, Indicators: links})
}

func handleV2GoalDelete(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid id"})
		return
	}
	res, err := tx.ExecContext(r.Context(), `DELETE FROM goals WHERE id = $1`, id)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"deleted": true})
}

type addLinkReq struct {
	IndicatorKind string `json:"indicator_kind"` // "catalog" | "tenant"
	IndicatorID   int64  `json:"indicator_id"`
	Role          string `json:"role,omitempty"`
}

func handleV2GoalAddIndicator(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	s := sessionFromContext(r.Context())
	idStr := chi.URLParam(r, "id")
	goalID, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid goal id"})
		return
	}
	var req addLinkReq
	if err := decodeJSON(r, &req); err != nil || req.IndicatorID == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "indicator_kind + indicator_id required"})
		return
	}
	if req.IndicatorKind != "catalog" && req.IndicatorKind != "tenant" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "indicator_kind must be catalog or tenant"})
		return
	}
	role := req.Role
	if role == "" {
		role = "driver"
	}
	// Verify goal belongs to caller's tenant (RLS handles it, but explicit error nicer)
	var goalOrg int64
	err = tx.QueryRowContext(r.Context(), `SELECT org_id FROM goals WHERE id = $1`, goalID).Scan(&goalOrg)
	if err == sql.ErrNoRows {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "goal not found"})
		return
	}
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}

	var linkID int64
	err = tx.QueryRowContext(r.Context(),
		`INSERT INTO goal_indicator_links (org_id, goal_id, indicator_kind, indicator_id, role)
		 VALUES ($1, $2, $3, $4, $5)
		 ON CONFLICT (goal_id, indicator_kind, indicator_id) DO UPDATE SET role = EXCLUDED.role
		 RETURNING id`,
		s.OrgID, goalID, req.IndicatorKind, req.IndicatorID, role,
	).Scan(&linkID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"id": linkID})
}

func handleV2GoalRemoveIndicator(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	idStr := chi.URLParam(r, "id")
	goalID, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid goal id"})
		return
	}
	linkIDStr := chi.URLParam(r, "linkId")
	linkID, err := strconv.ParseInt(linkIDStr, 10, 64)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid link id"})
		return
	}
	res, err := tx.ExecContext(r.Context(),
		`DELETE FROM goal_indicator_links WHERE id = $1 AND goal_id = $2`, linkID, goalID)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "link not found"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"deleted": true})
}

// loadGoalLinks pulls indicator links for a goal and joins to either catalog or tenant
// table to surface a human-readable code.
func loadGoalLinks(r *http.Request, tx *sql.Tx, goalID int64) ([]goalIndicatorLink, error) {
	q := `
		SELECT gil.id, gil.indicator_kind, gil.indicator_id, gil.role,
		       COALESCE(cit.code, ti.code) AS code
		  FROM goal_indicator_links gil
		  LEFT JOIN catalog_indicator_template cit
		         ON gil.indicator_kind = 'catalog' AND cit.id = gil.indicator_id
		  LEFT JOIN tenant_indicator ti
		         ON gil.indicator_kind = 'tenant'  AND ti.id = gil.indicator_id
		 WHERE gil.goal_id = $1
		 ORDER BY gil.added_at
	`
	rows, err := tx.QueryContext(r.Context(), q, goalID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []goalIndicatorLink{}
	for rows.Next() {
		var l goalIndicatorLink
		var code sql.NullString
		if err := rows.Scan(&l.ID, &l.IndicatorKind, &l.IndicatorID, &l.Role, &code); err != nil {
			continue
		}
		if code.Valid {
			l.IndicatorCode = code.String
		}
		out = append(out, l)
	}
	return out, nil
}
