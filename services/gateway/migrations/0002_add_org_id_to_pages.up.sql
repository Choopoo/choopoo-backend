-- Add org_id to existing tenant-data tables. Existing rows get sentinel org 0.
ALTER TABLE pages ADD COLUMN IF NOT EXISTS org_id BIGINT NOT NULL DEFAULT 0
    REFERENCES orgs(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_pages_org ON pages(org_id);
CREATE INDEX IF NOT EXISTS idx_pages_org_material ON pages(org_id, material);

ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS org_id BIGINT NOT NULL DEFAULT 0
    REFERENCES orgs(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_analysis_org ON analysis_results(org_id);
