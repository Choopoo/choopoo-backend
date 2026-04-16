-- Catalog (global, read-only by tenants) + supporting reference tables.
-- These tables have NO org_id and NO RLS. Service role writes; tenant_user
-- gets SELECT.

CREATE TABLE IF NOT EXISTS regions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    parent_id BIGINT REFERENCES regions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    trust_score NUMERIC(3,2) NOT NULL DEFAULT 0.5,
    lens_tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_families (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_cn TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS catalog_finished_product (
    id BIGSERIAL PRIMARY KEY,
    family_id BIGINT REFERENCES product_families(id),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_cn TEXT,
    default_region_code TEXT REFERENCES regions(code),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_raw_material (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_cn TEXT,
    unit TEXT NOT NULL DEFAULT 'CNY/ton',
    upstream_of_id BIGINT REFERENCES catalog_raw_material(id),
    category TEXT,                               -- isocyanate | polyol | solvent | catalyst | additive | macro
    volatility TEXT CHECK (volatility IN ('high','medium','low')),
    supply_risk TEXT CHECK (supply_risk IN ('high','medium','low')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_bom (
    id BIGSERIAL PRIMARY KEY,
    finished_product_id BIGINT NOT NULL REFERENCES catalog_finished_product(id) ON DELETE CASCADE,
    raw_material_id BIGINT NOT NULL REFERENCES catalog_raw_material(id) ON DELETE CASCADE,
    pct_of_cost NUMERIC(5,2),
    is_critical BOOLEAN DEFAULT FALSE,
    notes TEXT,
    UNIQUE(finished_product_id, raw_material_id)
);

GRANT SELECT ON regions, sources, product_families,
                catalog_finished_product, catalog_raw_material, catalog_bom
    TO tenant_user;
