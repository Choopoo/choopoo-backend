REVOKE ALL ON workflow_runs FROM tenant_user;
DROP TABLE IF EXISTS workflow_runs;
REVOKE ALL ON domain_events FROM tenant_user;
DROP TABLE IF EXISTS domain_events;
