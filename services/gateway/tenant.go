package main

import (
	"context"
	"crypto/subtle"
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
)

// ctxKey is a private type to avoid collisions on context keys.
type ctxKey string

const (
	ctxSessionKey ctxKey = "session"
)

// sessionFromContext returns the active session, or nil if unauthenticated.
func sessionFromContext(ctx context.Context) *Session {
	if v, ok := ctx.Value(ctxSessionKey).(*Session); ok {
		return v
	}
	return nil
}

// resolveSession middleware loads the session into context from one of two paths:
//   1. X-Service-Secret + X-Org-Id/X-User-Id/X-User-Role headers (trusted internal services)
//   2. Browser session cookie
// It does NOT reject missing sessions — requireAuth does that.
func resolveSession(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Trusted internal-service path. Constant-time compare so a wrong secret
		// can't leak length info via timing.
		if secret := getEnv("SERVICE_SECRET", ""); secret != "" {
			if subtle.ConstantTimeCompare([]byte(r.Header.Get("X-Service-Secret")), []byte(secret)) == 1 {
				if s := serviceSessionFromHeaders(r); s != nil {
					ctx := context.WithValue(r.Context(), ctxSessionKey, s)
					next.ServeHTTP(w, r.WithContext(ctx))
					return
				}
			}
		}
		// Browser cookie path.
		c, err := r.Cookie(sessionCookie)
		if err == nil && c.Value != "" {
			if s, err := loadSession(r.Context(), c.Value); err == nil {
				ctx := context.WithValue(r.Context(), ctxSessionKey, s)
				r = r.WithContext(ctx)
			}
		}
		next.ServeHTTP(w, r)
	})
}

// serviceSessionFromHeaders builds a synthetic session from X-Org-Id / X-User-Id /
// X-User-Role headers. Returns nil if any required header is missing or malformed.
func serviceSessionFromHeaders(r *http.Request) *Session {
	orgStr := r.Header.Get("X-Org-Id")
	userStr := r.Header.Get("X-User-Id")
	role := r.Header.Get("X-User-Role")
	if orgStr == "" || userStr == "" {
		return nil
	}
	orgID, err1 := strconv.ParseInt(orgStr, 10, 64)
	userID, err2 := strconv.ParseInt(userStr, 10, 64)
	if err1 != nil || err2 != nil {
		return nil
	}
	if role == "" {
		role = "owner"
	}
	return &Session{UserID: userID, OrgID: orgID, Role: role}
}

// requireAuth rejects unauthenticated requests.
func requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if sessionFromContext(r.Context()) == nil {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthenticated"})
			return
		}
		next.ServeHTTP(w, r)
	})
}

// withTenantTx opens a transaction, drops privileges to tenant_user, and sets
// app.org_id from the session. The transaction is exposed in context as ctxTxKey.
//
// On 5xx response or panic, the tx is rolled back. Otherwise commits.
//
// IMPORTANT: handlers that mutate must use TxFromContext(ctx) — using the global
// `db` would bypass RLS because that connection is the BYPASSRLS pipeline role.
func withTenantTx(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s := sessionFromContext(r.Context())
		if s == nil {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthenticated"})
			return
		}
		tx, err := db.BeginTx(r.Context(), nil)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "tx begin"})
			return
		}
		// SET LOCAL ROLE drops BYPASSRLS for the duration of this tx.
		if _, err := tx.ExecContext(r.Context(), "SET LOCAL ROLE tenant_user"); err != nil {
			_ = tx.Rollback()
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "set role"})
			return
		}
		// set_config(name, value, is_local=true) === SET LOCAL but parameterised safely.
		if _, err := tx.ExecContext(r.Context(),
			"SELECT set_config('app.org_id', $1, true)", strconv.FormatInt(s.OrgID, 10)); err != nil {
			_ = tx.Rollback()
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "set org"})
			return
		}

		ctx := context.WithValue(r.Context(), ctxTxKey, tx)
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

		defer func() {
			if p := recover(); p != nil {
				_ = tx.Rollback()
				panic(p)
			}
			if rec.status >= 500 {
				_ = tx.Rollback()
			} else {
				_ = tx.Commit()
			}
		}()

		next.ServeHTTP(rec, r.WithContext(ctx))
	})
}

// TxFromContext returns the active per-request transaction. Panics if none —
// programmer error to call tenant-scoped queries outside the middleware.
func TxFromContext(ctx context.Context) *sql.Tx {
	tx, ok := ctx.Value(ctxTxKey).(*sql.Tx)
	if !ok {
		panic("TxFromContext called without withTenantTx in chain")
	}
	return tx
}

const ctxTxKey ctxKey = "tenantTx"

// statusRecorder captures the response status so withTenantTx can decide
// commit vs. rollback after the handler returns.
type statusRecorder struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
}

func (sr *statusRecorder) WriteHeader(code int) {
	if !sr.wroteHeader {
		sr.status = code
		sr.wroteHeader = true
	}
	sr.ResponseWriter.WriteHeader(code)
}

func (sr *statusRecorder) Write(b []byte) (int, error) {
	if !sr.wroteHeader {
		sr.status = http.StatusOK
		sr.wroteHeader = true
	}
	return sr.ResponseWriter.Write(b)
}

// --- compatibility helpers for v2 handlers ---

func errMsg(err error) string {
	if err == nil {
		return ""
	}
	return fmt.Sprintf("%v", err)
}
