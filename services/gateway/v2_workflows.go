package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
)

type workflowRun struct {
	ID          int64           `json:"id"`
	Kind        string          `json:"kind"`
	SubjectRef  json.RawMessage `json:"subject_ref"`
	Plan        json.RawMessage `json:"plan"`
	State       string          `json:"state"`
	CurrentStep int             `json:"current_step"`
	StepsLog    json.RawMessage `json:"steps_log"`
	Error       *string         `json:"error"`
	StartedAt   string          `json:"started_at"`
	CompletedAt *string         `json:"completed_at"`
}

// GET /api/v2/workflows?goal_id=N — list saga runs for a given goal (or all).
func handleV2WorkflowsList(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	goalID := r.URL.Query().Get("goal_id")
	args := []interface{}{}
	q := `SELECT id, kind, subject_ref, COALESCE(plan, 'null'::jsonb), state, current_step,
	             COALESCE(steps_log, '[]'::jsonb), error, started_at, completed_at
	        FROM workflow_runs`
	if goalID != "" {
		q += ` WHERE subject_ref->>'goal_id' = $1`
		args = append(args, goalID)
	}
	q += ` ORDER BY id DESC LIMIT 20`
	rows, err := tx.QueryContext(r.Context(), q, args...)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	defer rows.Close()
	out := []workflowRun{}
	for rows.Next() {
		var wr workflowRun
		var subj, plan, log sql.NullString
		var errStr sql.NullString
		var started, completed sql.NullTime
		if err := rows.Scan(&wr.ID, &wr.Kind, &subj, &plan, &wr.State, &wr.CurrentStep, &log, &errStr, &started, &completed); err != nil {
			continue
		}
		if subj.Valid {
			wr.SubjectRef = json.RawMessage(subj.String)
		}
		if plan.Valid {
			wr.Plan = json.RawMessage(plan.String)
		}
		if log.Valid {
			wr.StepsLog = json.RawMessage(log.String)
		}
		wr.Error = nullStringPtr(errStr)
		if started.Valid {
			wr.StartedAt = started.Time.UTC().Format("2006-01-02T15:04:05Z")
		}
		if completed.Valid {
			s := completed.Time.UTC().Format("2006-01-02T15:04:05Z")
			wr.CompletedAt = &s
		}
		out = append(out, wr)
	}
	writeJSON(w, http.StatusOK, out)
}
