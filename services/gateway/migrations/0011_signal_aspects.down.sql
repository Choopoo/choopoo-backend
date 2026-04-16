REVOKE ALL ON aspect_consensus_readings, provider_readings, aspect_provider,
              subject_aspect_score, catalog_signal_aspect FROM tenant_user;
DROP TABLE IF EXISTS aspect_consensus_readings;
DROP TABLE IF EXISTS provider_readings;
DROP TABLE IF EXISTS aspect_provider;
DROP TABLE IF EXISTS subject_aspect_score;
DROP TABLE IF EXISTS catalog_signal_aspect;
