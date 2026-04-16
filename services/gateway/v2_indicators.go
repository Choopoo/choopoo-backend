package main

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
)

// GET /api/v2/indicators/{code}/latest — resolve an indicator code to a numeric
// value. If the indicator is composite (formula_json present), the value is
// computed recursively; otherwise the latest reading is returned.
func handleV2IndicatorLatest(w http.ResponseWriter, r *http.Request) {
	tx := TxFromContext(r.Context())
	code := chi.URLParam(r, "code")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code required"})
		return
	}
	v, ts, err := latestReadingByCode(r.Context(), tx, code)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	out := map[string]interface{}{"code": code, "value": v}
	if ts != nil {
		out["ts"] = *ts
	} else {
		out["ts"] = "computed"
	}
	writeJSON(w, http.StatusOK, out)
}

// POST /api/v2/test/indicator/reading — dev-only seed for catalog readings.
//   { "code": "TDI_SPOT_EC", "value": 15800, "ts": "2026-04-16T08:00:00Z" }
func handleV2TestIndicatorReading(w http.ResponseWriter, r *http.Request) {
	if getEnv("ENABLE_TEST_ENDPOINTS", "") != "1" {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	// Bypass per-request tenant_user — global_indicator_readings is service-role-write.
	// We use the global db pool (pipeline role, BYPASSRLS).
	var body struct {
		Code  string  `json:"code"`
		Value float64 `json:"value"`
		TS    string  `json:"ts"`
	}
	if err := decodeJSON(r, &body); err != nil || body.Code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code, value required"})
		return
	}
	ts := time.Now().UTC()
	if body.TS != "" {
		t, err := time.Parse(time.RFC3339, body.TS)
		if err == nil {
			ts = t
		}
	}

	var indID int64
	err := db.QueryRowContext(r.Context(),
		`SELECT id FROM catalog_indicator_template WHERE code = $1`, body.Code).Scan(&indID)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "no such catalog indicator: " + body.Code})
		return
	}
	if _, err := db.ExecContext(r.Context(),
		`INSERT INTO global_indicator_readings (indicator_id, ts, value, confidence)
		 VALUES ($1, $2, $3, 1.0)
		 ON CONFLICT (indicator_id, ts) DO UPDATE SET value = EXCLUDED.value`,
		indID, ts, body.Value); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}
