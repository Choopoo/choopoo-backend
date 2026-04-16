-- Goals = top-level user intent. Each goal links to indicators (catalog or tenant).

CREATE TABLE IF NOT EXISTS goals (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    lens TEXT NOT NULL CHECK (lens IN ('buy','sell','macro','mixed')),
    horizon_days INT,
    pinned BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_goals_org ON goals(org_id);
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
CREATE POLICY goals_select ON goals FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY goals_insert ON goals FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY goals_update ON goals FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY goals_delete ON goals FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

-- Polymorphic link: indicator_kind ∈ {'catalog','tenant'}, indicator_id is FK by kind.
-- We don't enforce FK at DB level (would require partitioned/conditional FK); enforced in app.
CREATE TABLE IF NOT EXISTS goal_indicator_links (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    goal_id BIGINT NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    indicator_kind TEXT NOT NULL CHECK (indicator_kind IN ('catalog','tenant')),
    indicator_id BIGINT NOT NULL,
    role TEXT NOT NULL DEFAULT 'driver' CHECK (role IN ('primary','driver','context')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (goal_id, indicator_kind, indicator_id)
);
CREATE INDEX IF NOT EXISTS idx_gil_goal ON goal_indicator_links(goal_id);
ALTER TABLE goal_indicator_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY gil_select ON goal_indicator_links FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY gil_insert ON goal_indicator_links FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY gil_delete ON goal_indicator_links FOR DELETE USING (org_id = current_setting('app.org_id', true)::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON goals, goal_indicator_links TO tenant_user;
-- New sequences won't be picked up by the earlier "ALL SEQUENCES" grant; grant explicitly.
GRANT USAGE, SELECT ON SEQUENCE goals_id_seq, goal_indicator_links_id_seq TO tenant_user;
