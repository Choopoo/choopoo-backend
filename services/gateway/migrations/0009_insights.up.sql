-- Insights = AI-generated narratives, traceable to evidence (article pages + indicator readings).

CREATE TABLE IF NOT EXISTS insights (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    goal_id BIGINT REFERENCES goals(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('briefing','alert','forecast','event','recommendation')),
    title TEXT NOT NULL,
    body_md TEXT NOT NULL,
    ai_model TEXT,                                 -- e.g. 'claude-opus-4-7', NULL for rule-based
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_insights_org_created ON insights(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_goal ON insights(goal_id);
ALTER TABLE insights ENABLE ROW LEVEL SECURITY;
CREATE POLICY insights_select ON insights FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY insights_insert ON insights FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY insights_update ON insights FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY insights_delete ON insights FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Polymorphic evidence: a single insight can cite article pages AND time-series readings.
-- Exactly one of (page_id, catalog_indicator_id, tenant_indicator_id) is non-null.
CREATE TABLE IF NOT EXISTS insight_evidence (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    insight_id BIGINT NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN ('page','catalog_indicator','tenant_indicator')),
    page_id BIGINT REFERENCES pages(id) ON DELETE SET NULL,
    catalog_indicator_id BIGINT REFERENCES catalog_indicator_template(id) ON DELETE SET NULL,
    tenant_indicator_id BIGINT REFERENCES tenant_indicator(id) ON DELETE SET NULL,
    reading_ts TIMESTAMPTZ,
    weight NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (evidence_kind = 'page' AND page_id IS NOT NULL AND catalog_indicator_id IS NULL AND tenant_indicator_id IS NULL)
     OR (evidence_kind = 'catalog_indicator' AND catalog_indicator_id IS NOT NULL AND page_id IS NULL AND tenant_indicator_id IS NULL)
     OR (evidence_kind = 'tenant_indicator' AND tenant_indicator_id IS NOT NULL AND page_id IS NULL AND catalog_indicator_id IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_insight_evidence_insight ON insight_evidence(insight_id);
ALTER TABLE insight_evidence ENABLE ROW LEVEL SECURITY;
CREATE POLICY ie_select ON insight_evidence FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY ie_insert ON insight_evidence FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY ie_delete ON insight_evidence FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON insights, insight_evidence TO tenant_user;
GRANT USAGE, SELECT ON SEQUENCE insights_id_seq, insight_evidence_id_seq TO tenant_user;
