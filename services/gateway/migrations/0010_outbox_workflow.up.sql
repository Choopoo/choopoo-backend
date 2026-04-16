-- Transactional outbox: every tenant-scoped write that triggers an async workflow
-- inserts a row here IN THE SAME TX. A relay goroutine in gateway publishes
-- unpublished rows to Kafka at-least-once, then marks them published.
--
-- This is the canonical "dual write problem" solution: guarantees that if the DB
-- commit happens, the event WILL reach Kafka (eventually), and we never publish
-- a phantom event for a rolled-back tx.
--
-- NOT RLS-enabled: writes are done by the same tx as the triggering entity
-- (so RLS is satisfied via session role), reads are done by the pipeline
-- BYPASSRLS relay. Access is service-role-only; no direct tenant access.

CREATE TABLE IF NOT EXISTS domain_events (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_domain_events_unpublished
    ON domain_events(created_at) WHERE published_at IS NULL;
GRANT INSERT ON domain_events TO tenant_user;
GRANT USAGE, SELECT ON SEQUENCE domain_events_id_seq TO tenant_user;

-- Saga state for long-running workflows (autopilot, investigation, briefing).
-- RLS-enabled so tenants see their own workflow runs only.
CREATE TABLE IF NOT EXISTS workflow_runs (
    id BIGSERIAL PRIMARY KEY,
    org_id BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                      -- e.g. 'goal_to_data'
    trigger_event_id BIGINT REFERENCES domain_events(id),
    subject_ref JSONB,                       -- e.g. {"goal_id": 12}
    plan JSONB,                              -- list of step defs
    state TEXT NOT NULL DEFAULT 'planning'
        CHECK (state IN ('planning','running','succeeded','failed','compensating','compensated')),
    current_step INT DEFAULT 0,
    steps_log JSONB DEFAULT '[]'::jsonb,     -- append-only execution log
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_org ON workflow_runs(org_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_subject ON workflow_runs((subject_ref->>'goal_id'));
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY wr_select ON workflow_runs FOR SELECT USING (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY wr_insert ON workflow_runs FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
CREATE POLICY wr_update ON workflow_runs FOR UPDATE USING (org_id = current_setting('app.org_id', true)::bigint);
GRANT SELECT, INSERT, UPDATE ON workflow_runs TO tenant_user;
GRANT USAGE, SELECT ON SEQUENCE workflow_runs_id_seq TO tenant_user;
