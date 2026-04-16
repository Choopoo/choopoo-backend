-- Signal aspects — an information-content layer above sources.
-- An *aspect* is a distinct axis of info (price, weather, supply_event, …).
-- Subjects (raw materials, finished products) get a ranked set of aspects
-- to activate; each aspect can be fed by multiple providers.
--
-- Anti-hallucination: each LLM-proposed aspect carries a structured induction
-- chain + cited example events so the owner (and the synthesiser) can audit
-- the proposal rather than trusting it blindly.

CREATE TABLE IF NOT EXISTS catalog_signal_aspect (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    axis TEXT NOT NULL CHECK (axis IN (
        'price','supply_event','shipping','regulatory','weather',
        'trade_flow','geopolitics','demand_proxy','capacity_news','macro_fx')),
    default_relevance NUMERIC(4,3) NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
GRANT SELECT ON catalog_signal_aspect TO tenant_user;

-- Per-subject aspect ranking. Global (not tenant-scoped) — the library of
-- which aspects matter for each material is the same across tenants for v1.
-- evidence_verified starts FALSE (LLM-claimed); a background resolver flips it
-- TRUE when the cited example events are matched against real pages/readings.
CREATE TABLE IF NOT EXISTS subject_aspect_score (
    subject_code TEXT NOT NULL,
    aspect_id BIGINT NOT NULL REFERENCES catalog_signal_aspect(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('active','candidate','rejected')),
    relevance_r NUMERIC(4,3),
    diversity_bonus NUMERIC(4,3),
    score NUMERIC(4,3),
    relevance_rationale TEXT,
    induction_chain JSONB,       -- [{step:1, cause:"..."}, {step:2, effect:"..."}, …]
    example_events JSONB,        -- [{date, event, observed_impact, source_url, verified}]
    evidence_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_scored_at TIMESTAMPTZ,
    reviewed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (subject_code, aspect_id)
);
CREATE INDEX IF NOT EXISTS idx_sas_subject ON subject_aspect_score(subject_code, status);
GRANT SELECT ON subject_aspect_score TO tenant_user;

-- Multi-provider registry per aspect (0..n providers per aspect).
-- E.g. the `price` aspect has providers: 100ppi.com, sci99.com, oilchem.net.
CREATE TABLE IF NOT EXISTS aspect_provider (
    id BIGSERIAL PRIMARY KEY,
    aspect_id BIGINT NOT NULL REFERENCES catalog_signal_aspect(id) ON DELETE CASCADE,
    source_id BIGINT REFERENCES sources(id) ON DELETE SET NULL,
    schema_hint JSONB,           -- how to parse this provider (fetch strategy)
    update_freq_minutes INT NOT NULL DEFAULT 1440,
    trust_score NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'healthy'
        CHECK (status IN ('healthy','stale','broken')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ap_aspect ON aspect_provider(aspect_id);
GRANT SELECT ON aspect_provider TO tenant_user;

-- Raw per-provider readings — facts straight from source. Keyed by provider
-- so duplicate sources of the same price don't clobber one another.
CREATE TABLE IF NOT EXISTS provider_readings (
    provider_id BIGINT NOT NULL REFERENCES aspect_provider(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    value NUMERIC,
    raw_excerpt TEXT,
    PRIMARY KEY (provider_id, subject_code, ts)
);

-- Fused consensus series per (aspect, subject). Populated by a consensus
-- fuser service (future) from provider_readings. For MVP this may remain
-- empty; UI shows the highest-trust single provider as a fallback.
CREATE TABLE IF NOT EXISTS aspect_consensus_readings (
    aspect_id BIGINT NOT NULL REFERENCES catalog_signal_aspect(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    value_consensus NUMERIC,
    divergence NUMERIC,          -- stdev of providers at this timestamp
    provider_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (aspect_id, subject_code, ts)
);
