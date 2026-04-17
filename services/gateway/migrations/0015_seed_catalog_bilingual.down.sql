-- Reverse the source-label split. The other backfills are non-destructive
-- (we only added Chinese / friendlier-name columns which we'll wipe).
UPDATE sources SET label = label_cn || ' ' || label
    WHERE label_cn IS NOT NULL;

UPDATE catalog_signal_aspect SET name_cn = NULL, description_cn = NULL;
UPDATE catalog_indicator_template SET name = NULL, name_cn = NULL, description_cn = NULL;
