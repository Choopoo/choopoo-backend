REVOKE ALL ON catalog_indicator_template, global_indicator_readings FROM tenant_user;
DROP TABLE IF EXISTS global_indicator_readings;
DROP INDEX IF EXISTS idx_indicator_subject;
DROP TABLE IF EXISTS catalog_indicator_template;
