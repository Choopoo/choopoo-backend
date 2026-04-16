-- Seed is data-only; nothing to drop schema-wise. Truncate to revert.
TRUNCATE catalog_indicator_template, catalog_bom, catalog_finished_product,
         catalog_raw_material, product_families, sources, regions
    RESTART IDENTITY CASCADE;
