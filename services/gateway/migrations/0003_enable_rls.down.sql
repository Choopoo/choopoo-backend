DROP POLICY IF EXISTS analysis_tenant_insert ON analysis_results;
DROP POLICY IF EXISTS analysis_tenant_select ON analysis_results;
ALTER TABLE analysis_results DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pages_tenant_delete ON pages;
DROP POLICY IF EXISTS pages_tenant_update ON pages;
DROP POLICY IF EXISTS pages_tenant_insert ON pages;
DROP POLICY IF EXISTS pages_tenant_select ON pages;
ALTER TABLE pages DISABLE ROW LEVEL SECURITY;

ALTER ROLE pipeline NOBYPASSRLS;

REVOKE ALL ON pages, analysis_results FROM tenant_user;
REVOKE tenant_user FROM pipeline;
DROP ROLE IF EXISTS tenant_user;
