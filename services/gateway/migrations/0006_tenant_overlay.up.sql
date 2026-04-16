-- Tenant overlay tables: enablements, overrides, private additions.
-- All RLS-enabled and scoped by app.org_id GUC set in the per-request tx.

-- Enable a catalog raw material (with optional local nickname).
CREATE TABLE IF NOT EXISTS tenant_raw_material_enablement (
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    catalog_raw_material_id BIGINT NOT NULL REFERENCES catalog_raw_material(id) ON DELETE CASCADE,
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nickname TEXT,
    PRIMARY KEY (org_id, catalog_raw_material_id)
);
ALTER TABLE tenant_raw_material_enablement ENABLE ROW LEVEL SECURITY;
CREATE POLICY trme_select ON tenant_raw_material_enablement
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trme_insert ON tenant_raw_material_enablement
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trme_update ON tenant_raw_material_enablement
    FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trme_delete ON tenant_raw_material_enablement
    FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Private raw material (caprolactam, etc — anything not yet in catalog).
CREATE TABLE IF NOT EXISTS tenant_raw_material (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    name_cn TEXT,
    unit TEXT NOT NULL DEFAULT 'CNY/ton',
    upstream_of_ref JSONB,                -- {kind: 'catalog'|'tenant', id: ...}
    category TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, code)
);
ALTER TABLE tenant_raw_material ENABLE ROW LEVEL SECURITY;
CREATE POLICY trm_select ON tenant_raw_material
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trm_insert ON tenant_raw_material
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trm_update ON tenant_raw_material
    FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY trm_delete ON tenant_raw_material
    FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Enable a catalog indicator template.
CREATE TABLE IF NOT EXISTS tenant_indicator_enablement (
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    catalog_indicator_template_id BIGINT NOT NULL REFERENCES catalog_indicator_template(id) ON DELETE CASCADE,
    role TEXT,                            -- e.g. 'primary'|'driver'|'context' (free-form, used by goal_indicator_links later)
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, catalog_indicator_template_id)
);
ALTER TABLE tenant_indicator_enablement ENABLE ROW LEVEL SECURITY;
CREATE POLICY tie_select ON tenant_indicator_enablement
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tie_insert ON tenant_indicator_enablement
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tie_update ON tenant_indicator_enablement
    FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tie_delete ON tenant_indicator_enablement
    FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Override the formula/cadence/source of a catalog indicator (keeps the same id).
CREATE TABLE IF NOT EXISTS tenant_indicator_override (
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    catalog_indicator_template_id BIGINT NOT NULL REFERENCES catalog_indicator_template(id) ON DELETE CASCADE,
    formula_json_override JSONB,
    cadence_override INT,
    source_override BIGINT REFERENCES sources(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, catalog_indicator_template_id)
);
ALTER TABLE tenant_indicator_override ENABLE ROW LEVEL SECURITY;
CREATE POLICY tio_select ON tenant_indicator_override
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tio_insert ON tenant_indicator_override
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tio_update ON tenant_indicator_override
    FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tio_delete ON tenant_indicator_override
    FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Fully private composite indicators.
CREATE TABLE IF NOT EXISTS tenant_indicator (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    kind TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    subject_ref JSONB,
    region_code TEXT,
    unit TEXT NOT NULL,
    cadence_minutes INT NOT NULL DEFAULT 1440,
    source_ref JSONB,
    formula_json JSONB,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, code)
);
ALTER TABLE tenant_indicator ENABLE ROW LEVEL SECURITY;
CREATE POLICY ti_select ON tenant_indicator
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY ti_insert ON tenant_indicator
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY ti_update ON tenant_indicator
    FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY ti_delete ON tenant_indicator
    FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

CREATE TABLE IF NOT EXISTS tenant_indicator_readings (
    tenant_indicator_id BIGINT NOT NULL REFERENCES tenant_indicator(id) ON DELETE CASCADE,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    value NUMERIC NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    source_page_id BIGINT,
    PRIMARY KEY (tenant_indicator_id, ts)
);
ALTER TABLE tenant_indicator_readings ENABLE ROW LEVEL SECURITY;
CREATE POLICY tir_select ON tenant_indicator_readings
    FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY tir_insert ON tenant_indicator_readings
    FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenant_raw_material_enablement,
    tenant_raw_material,
    tenant_indicator_enablement,
    tenant_indicator_override,
    tenant_indicator,
    tenant_indicator_readings
    TO tenant_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tenant_user;
