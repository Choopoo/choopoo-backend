-- Sentinel org_id = 0 represents the legacy/system tenant for v1 endpoints.
CREATE TABLE IF NOT EXISTS orgs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO orgs (id, name, domain) VALUES (0, 'system', NULL)
ON CONFLICT (id) DO NOTHING;
SELECT setval(pg_get_serial_sequence('orgs','id'), GREATEST((SELECT MAX(id) FROM orgs), 1));

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner','analyst')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);

-- Magic-link token storage (server-side, single-use)
CREATE TABLE IF NOT EXISTS magic_link_tokens (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_magic_link_email ON magic_link_tokens(email);
