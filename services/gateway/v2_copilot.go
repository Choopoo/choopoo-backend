package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"time"
)

// POST /api/v2/copilot/converse
//
// Proxies the user's message to the copilot service, forwarding the session
// identity in headers signed by SERVICE_SECRET. Copilot uses the same headers
// when calling back into gateway, so RLS enforcement is end-to-end identical
// to a direct user request.
//
// This handler intentionally lives OUTSIDE withTenantTx — it's an HTTP proxy,
// not a DB call.
func handleV2CopilotConverse(w http.ResponseWriter, r *http.Request) {
	s := sessionFromContext(r.Context())
	if s == nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthenticated"})
		return
	}

	var req struct {
		Message string                   `json:"message"`
		History []map[string]interface{} `json:"history,omitempty"`
	}
	if err := decodeJSON(r, &req); err != nil || req.Message == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "message required"})
		return
	}

	body := map[string]interface{}{
		"message": req.Message,
		"ctx": map[string]interface{}{
			"user_id": s.UserID,
			"org_id":  s.OrgID,
			"role":    s.Role,
		},
	}
	if req.History != nil {
		body["history"] = req.History
	}
	payload, _ := json.Marshal(body)

	copilotURL := getEnv("COPILOT_URL", "http://copilot:8090")
	pReq, _ := http.NewRequestWithContext(r.Context(), "POST", copilotURL+"/converse", bytes.NewReader(payload))
	pReq.Header.Set("Content-Type", "application/json")
	pReq.Header.Set("X-Service-Secret", getEnv("SERVICE_SECRET", ""))

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(pReq)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "copilot unreachable: " + err.Error()})
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}
