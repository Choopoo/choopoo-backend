ALTER TABLE users DROP COLUMN IF EXISTS locale;
ALTER TABLE sources DROP COLUMN IF EXISTS label_cn;
ALTER TABLE catalog_signal_aspect
    DROP COLUMN IF EXISTS description_cn,
    DROP COLUMN IF EXISTS name_cn;
ALTER TABLE catalog_indicator_template
    DROP COLUMN IF EXISTS description_cn,
    DROP COLUMN IF EXISTS name_cn,
    DROP COLUMN IF EXISTS name;
