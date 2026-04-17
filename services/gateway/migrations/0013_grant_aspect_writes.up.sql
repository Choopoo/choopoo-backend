-- subject_aspect_score is global (not tenant-scoped), but copilot's
-- propose_aspect tool runs as tenant_user inside withTenantTx. Grant write
-- access so the tool can upsert proposals.
GRANT INSERT, UPDATE ON subject_aspect_score TO tenant_user;
