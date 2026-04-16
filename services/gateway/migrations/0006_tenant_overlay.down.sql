REVOKE ALL ON
    tenant_raw_material_enablement,
    tenant_raw_material,
    tenant_indicator_enablement,
    tenant_indicator_override,
    tenant_indicator,
    tenant_indicator_readings
    FROM tenant_user;
DROP TABLE IF EXISTS tenant_indicator_readings;
DROP TABLE IF EXISTS tenant_indicator;
DROP TABLE IF EXISTS tenant_indicator_override;
DROP TABLE IF EXISTS tenant_indicator_enablement;
DROP TABLE IF EXISTS tenant_raw_material;
DROP TABLE IF EXISTS tenant_raw_material_enablement;
