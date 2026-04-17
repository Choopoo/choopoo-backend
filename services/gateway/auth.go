package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"net/mail"
	"strings"
	"time"
)

const (
	magicLinkTTL  = 15 * time.Minute
	sessionCookie = "choopoo_session"
)

type magicLinkRequest struct {
	Email string `json:"email"`
}

type magicLinkResponse struct {
	Sent      bool   `json:"sent"`
	DevLink   string `json:"dev_link,omitempty"` // surfaced in dev mode for now (no SMTP wired)
	ExpiresIn int64  `json:"expires_in"`
}

type meResponse struct {
	UserID int64  `json:"user_id"`
	OrgID  int64  `json:"org_id"`
	Email  string `json:"email"`
	Locale string `json:"locale"`
	Role   string `json:"role"`
}

// POST /auth/magic-link  { email } -> creates a single-use token, "sends" it.
// In dev (SMTP_FROM unset), returns the link directly in the response so the
// integration test and the demo flow can complete without an SMTP gateway.
func handleRequestMagicLink(w http.ResponseWriter, r *http.Request) {
	var req magicLinkRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}
	addr, err := mail.ParseAddress(strings.TrimSpace(req.Email))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid email"})
		return
	}
	email := strings.ToLower(addr.Address)

	token, err := randomToken(32)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "token gen"})
		return
	}
	expiresAt := time.Now().Add(magicLinkTTL)
	if _, err := db.ExecContext(r.Context(),
		`INSERT INTO magic_link_tokens (token, email, expires_at) VALUES ($1, $2, $3)`,
		token, email, expiresAt); err != nil {
		log.Printf("magic-link insert: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store token"})
		return
	}

	link := buildMagicLink(r, token)
	resp := magicLinkResponse{Sent: true, ExpiresIn: int64(magicLinkTTL.Seconds())}
	if getEnv("SMTP_FROM", "") == "" {
		// Dev mode: surface the link so a script/UI can complete sign-in without email.
		resp.DevLink = link
		log.Printf("[DEV] magic link for %s: %s", email, link)
	} else {
		// TODO: wire real SMTP here in a later step.
		log.Printf("magic link for %s (would send via SMTP): %s", email, link)
	}
	writeJSON(w, http.StatusOK, resp)
}

// GET /auth/verify?token=...  -> consume token, set session cookie, redirect to /
func handleVerifyMagicLink(w http.ResponseWriter, r *http.Request) {
	token := strings.TrimSpace(r.URL.Query().Get("token"))
	if token == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing token"})
		return
	}

	var email string
	var expiresAt time.Time
	var consumedAt *time.Time
	err := db.QueryRowContext(r.Context(),
		`SELECT email, expires_at, consumed_at FROM magic_link_tokens WHERE token = $1`, token,
	).Scan(&email, &expiresAt, &consumedAt)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid token"})
		return
	}
	if consumedAt != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "token already used"})
		return
	}
	if time.Now().After(expiresAt) {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "token expired"})
		return
	}

	// Mark consumed (single-use).
	if _, err := db.ExecContext(r.Context(),
		`UPDATE magic_link_tokens SET consumed_at = NOW() WHERE token = $1`, token); err != nil {
		log.Printf("token consume: %v", err)
	}

	// Provision (or load) org + user.
	user, err := provisionUser(r.Context(), email)
	if err != nil {
		log.Printf("provisionUser: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "provision"})
		return
	}

	sid := newSessionID()
	sess := Session{
		UserID:    user.ID,
		OrgID:     user.OrgID,
		Email:     user.Email,
		Role:      user.Role,
		ExpiresAt: time.Now().Add(sessionTTL).Unix(),
	}
	if err := storeSession(r.Context(), sid, sess); err != nil {
		log.Printf("storeSession: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "session"})
		return
	}

	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    sid,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   r.TLS != nil,
		Expires:  time.Now().Add(sessionTTL),
	})

	// If a Redirect is set, follow it; otherwise return JSON.
	if redirect := r.URL.Query().Get("redirect"); redirect != "" {
		http.Redirect(w, r, redirect, http.StatusFound)
		return
	}
	var locale string
	if err := db.QueryRowContext(r.Context(),
		`SELECT locale FROM users WHERE id = $1`, user.ID).Scan(&locale); err != nil {
		locale = "en"
	}
	writeJSON(w, http.StatusOK, meResponse{
		UserID: user.ID, OrgID: user.OrgID, Email: user.Email, Role: user.Role, Locale: locale,
	})
}

// POST /auth/logout
func handleLogout(w http.ResponseWriter, r *http.Request) {
	c, err := r.Cookie(sessionCookie)
	if err == nil {
		_ = deleteSession(r.Context(), c.Value)
	}
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		MaxAge:   -1,
	})
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

// GET /api/v2/me  -- returns current user/org from session.
func handleMe(w http.ResponseWriter, r *http.Request) {
	s := sessionFromContext(r.Context())
	if s == nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthenticated"})
		return
	}
	var locale string
	if err := db.QueryRowContext(r.Context(),
		`SELECT locale FROM users WHERE id = $1`, s.UserID).Scan(&locale); err != nil {
		locale = "en"
	}
	writeJSON(w, http.StatusOK, meResponse{
		UserID: s.UserID, OrgID: s.OrgID, Email: s.Email, Role: s.Role, Locale: locale,
	})
}

// PATCH /api/v2/me -- update the current user's locale preference.
func handleUpdateMe(w http.ResponseWriter, r *http.Request) {
	s := sessionFromContext(r.Context())
	if s == nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthenticated"})
		return
	}
	var body struct {
		Locale string `json:"locale"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "body required"})
		return
	}
	if body.Locale != "en" && body.Locale != "zh-CN" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "locale must be 'en' or 'zh-CN'"})
		return
	}
	if _, err := db.ExecContext(r.Context(),
		`UPDATE users SET locale = $1 WHERE id = $2`, body.Locale, s.UserID); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": errMsg(err)})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"locale": body.Locale})
}

// --- helpers ---

type provisionedUser struct {
	ID    int64
	OrgID int64
	Email string
	Role  string
}

// provisionUser ensures an org (by email domain) and a user exist for the given email.
// First user of an org becomes 'owner'; subsequent users default to 'analyst'.
func provisionUser(ctx context.Context, email string) (*provisionedUser, error) {
	domain := emailDomain(email)
	if domain == "" {
		return nil, errors.New("email has no domain")
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()

	var orgID int64
	err = tx.QueryRowContext(ctx, `SELECT id FROM orgs WHERE domain = $1`, domain).Scan(&orgID)
	if err != nil {
		// Create org. Name = domain for now; user can rename later.
		err = tx.QueryRowContext(ctx,
			`INSERT INTO orgs (name, domain) VALUES ($1, $1) RETURNING id`, domain).Scan(&orgID)
		if err != nil {
			return nil, err
		}
	}

	// Existing user?
	var u provisionedUser
	err = tx.QueryRowContext(ctx,
		`SELECT id, org_id, email, role FROM users WHERE email = $1`, email,
	).Scan(&u.ID, &u.OrgID, &u.Email, &u.Role)
	if err == nil {
		_, _ = tx.ExecContext(ctx, `UPDATE users SET last_login_at = NOW() WHERE id = $1`, u.ID)
		return &u, tx.Commit()
	}

	// New user. First user of org = owner; later users = analyst.
	var hasUsers bool
	_ = tx.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM users WHERE org_id = $1)`, orgID).Scan(&hasUsers)
	role := "owner"
	if hasUsers {
		role = "analyst"
	}

	err = tx.QueryRowContext(ctx,
		`INSERT INTO users (org_id, email, role, last_login_at)
		 VALUES ($1, $2, $3, NOW()) RETURNING id, org_id, email, role`,
		orgID, email, role,
	).Scan(&u.ID, &u.OrgID, &u.Email, &u.Role)
	if err != nil {
		return nil, err
	}
	return &u, tx.Commit()
}

func emailDomain(email string) string {
	at := strings.LastIndex(email, "@")
	if at < 0 || at == len(email)-1 {
		return ""
	}
	return strings.ToLower(email[at+1:])
}

func randomToken(nBytes int) (string, error) {
	b := make([]byte, nBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func buildMagicLink(r *http.Request, token string) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	host := getEnv("PUBLIC_HOST", r.Host)
	return scheme + "://" + host + "/auth/verify?token=" + token
}
