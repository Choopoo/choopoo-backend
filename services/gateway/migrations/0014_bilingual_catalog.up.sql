-- Bilingual catalog + user locale preference.
--
-- IMPORT_PARITY_TDI was leaking the engineering code as a primary label
-- because catalog_indicator_template had no human name. Three tables
-- already follow the (name, name_cn) pattern (catalog_raw_material,
-- catalog_finished_product, product_families); this migration extends
-- the same pattern to the four tables that were English-only.
--
-- Also adds users.locale so a Chinese-server deploy can pin the default
-- and the AvatarMenu switcher can persist a user's choice.

ALTER TABLE catalog_indicator_template
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS name_cn TEXT,
    ADD COLUMN IF NOT EXISTS description_cn TEXT;

ALTER TABLE catalog_signal_aspect
    ADD COLUMN IF NOT EXISTS name_cn TEXT,
    ADD COLUMN IF NOT EXISTS description_cn TEXT;

-- sources currently mashes both locales into a single label like
-- "生意社 Sunsirs". Split into label (English) + label_cn (Chinese).
ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS label_cn TEXT;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS locale TEXT NOT NULL DEFAULT 'en'
        CHECK (locale IN ('en', 'zh-CN'));
