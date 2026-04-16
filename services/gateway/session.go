package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
)

const sessionTTL = 7 * 24 * time.Hour

type Session struct {
	UserID    int64  `json:"user_id"`
	OrgID     int64  `json:"org_id"`
	Email     string `json:"email"`
	Role      string `json:"role"`
	ExpiresAt int64  `json:"exp"`
}

func newSessionID() string {
	return uuid.NewString()
}

func sessionKey(id string) string {
	return "session:" + id
}

func storeSession(ctx context.Context, id string, s Session) error {
	data, err := json.Marshal(s)
	if err != nil {
		return err
	}
	return rdb.Set(ctx, sessionKey(id), data, sessionTTL).Err()
}

func loadSession(ctx context.Context, id string) (*Session, error) {
	raw, err := rdb.Get(ctx, sessionKey(id)).Bytes()
	if err != nil {
		return nil, err
	}
	var s Session
	if err := json.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	if s.ExpiresAt > 0 && time.Now().Unix() > s.ExpiresAt {
		_ = rdb.Del(ctx, sessionKey(id)).Err()
		return nil, fmt.Errorf("session expired")
	}
	return &s, nil
}

func deleteSession(ctx context.Context, id string) error {
	return rdb.Del(ctx, sessionKey(id)).Err()
}
