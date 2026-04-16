-- Indicator catalog: a template defines how to compute a metric.
--   formula_json NULL  -> direct reading (e.g. raw spot price scraped from a source)
--   formula_json {...} -> derived (e.g. spread between two other indicators)

CREATE TABLE IF NOT EXISTS catalog_indicator_template (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('price','demand','supply','macro','regulatory','spread','derived')),
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('raw_material','finished_product','region','macro_series')),
    subject_code TEXT,                    -- code of subject (FK by code, not strict)
    region_code TEXT REFERENCES regions(code),
    unit TEXT NOT NULL,
    cadence_minutes INT NOT NULL DEFAULT 1440,
    source_id BIGINT REFERENCES sources(id),
    formula_json JSONB,                   -- {op: "subtract", left: {indicator_code: ...}, right: {...}}
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicator_subject ON catalog_indicator_template(subject_kind, subject_code);

-- Time-series readings for catalog indicators (shared across tenants).
CREATE TABLE IF NOT EXISTS global_indicator_readings (
    indicator_id BIGINT NOT NULL REFERENCES catalog_indicator_template(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    value NUMERIC NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    source_page_id BIGINT,                -- intentionally not FK -> pages so cross-tenant page rows don't poison RLS
    PRIMARY KEY (indicator_id, ts)
);

GRANT SELECT ON catalog_indicator_template, global_indicator_readings TO tenant_user;
