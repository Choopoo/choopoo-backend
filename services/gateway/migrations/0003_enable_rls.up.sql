-- RLS strategy:
-- * `pipeline` role keeps BYPASSRLS — used by consumer/ai-service and by gateway-at-startup
--   (migrations, system reads). Existing v1 services unaffected.
-- * Gateway middleware drops privilege per request via `SET LOCAL ROLE tenant_user`.
--   `tenant_user` does NOT have BYPASSRLS, so RLS policies are enforced on every
--   tenant-scoped query inside that transaction.
-- * `app.org_id` GUC drives the policy predicate.

-- Create tenant_user if missing. Grant pipeline the ability to SET ROLE tenant_user.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tenant_user') THEN
        CREATE ROLE tenant_user NOINHERIT;
    END IF;
END $$;
GRANT tenant_user TO pipeline;

-- tenant_user can read/write tenant tables; RLS will further restrict per row.
GRANT SELECT, INSERT, UPDATE, DELETE ON pages, analysis_results TO tenant_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tenant_user;

-- Pipeline role bypasses RLS for service-role workloads.
ALTER ROLE pipeline BYPASSRLS;

ALTER TABLE pages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pages_tenant_select ON pages;
CREATE POLICY pages_tenant_select ON pages
    FOR SELECT
    USING (org_id = current_setting('app.org_id', true)::bigint);
DROP POLICY IF EXISTS pages_tenant_insert ON pages;
CREATE POLICY pages_tenant_insert ON pages
    FOR INSERT
    WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
DROP POLICY IF EXISTS pages_tenant_update ON pages;
CREATE POLICY pages_tenant_update ON pages
    FOR UPDATE
    USING (org_id = current_setting('app.org_id', true)::bigint);
DROP POLICY IF EXISTS pages_tenant_delete ON pages;
CREATE POLICY pages_tenant_delete ON pages
    FOR DELETE
    USING (org_id = current_setting('app.org_id', true)::bigint);

ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS analysis_tenant_select ON analysis_results;
CREATE POLICY analysis_tenant_select ON analysis_results
    FOR SELECT
    USING (org_id = current_setting('app.org_id', true)::bigint);
DROP POLICY IF EXISTS analysis_tenant_insert ON analysis_results;
CREATE POLICY analysis_tenant_insert ON analysis_results
    FOR INSERT
    WITH CHECK (org_id = current_setting('app.org_id', true)::bigint);
