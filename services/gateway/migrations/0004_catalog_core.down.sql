REVOKE ALL ON regions, sources, product_families,
              catalog_finished_product, catalog_raw_material, catalog_bom
    FROM tenant_user;
DROP TABLE IF EXISTS catalog_bom;
DROP TABLE IF EXISTS catalog_raw_material;
DROP TABLE IF EXISTS catalog_finished_product;
DROP TABLE IF EXISTS product_families;
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS regions;
