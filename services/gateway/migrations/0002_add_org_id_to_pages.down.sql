DROP INDEX IF EXISTS idx_analysis_org;
ALTER TABLE analysis_results DROP COLUMN IF EXISTS org_id;
DROP INDEX IF EXISTS idx_pages_org_material;
DROP INDEX IF EXISTS idx_pages_org;
ALTER TABLE pages DROP COLUMN IF EXISTS org_id;
