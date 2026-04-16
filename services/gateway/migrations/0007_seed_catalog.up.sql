-- Seed catalog with PU-SME baseline. Per design, polyether polyols and PU foams
-- are EXCLUDED (a 60K t/y hardener-focused SME does not run those reactor lines).
-- Owner can add via the inline Goal-wizard authoring flow if customer profile differs.
--
-- All inserts are idempotent via ON CONFLICT DO NOTHING.

-- regions
INSERT INTO regions (code, name) VALUES
    ('CN-EC', '华东 (East China)'),
    ('CN-NC', '华北 (North China)'),
    ('CN-SC', '华南 (South China)'),
    ('CN', 'China (national)'),
    ('GLOBAL', 'Global')
ON CONFLICT (code) DO NOTHING;

-- sources
INSERT INTO sources (domain, label, trust_score, lens_tags) VALUES
    ('100ppi.com',     '生意社 Sunsirs',       0.85, ARRAY['price','spot']),
    ('sci99.com',      '卓创资讯 Sublime',     0.85, ARRAY['price','maintenance']),
    ('oilchem.net',    '隆众资讯 Longzhong',   0.85, ARRAY['price','import_parity']),
    ('baiinfo.com',    '百川盈孚 Baiinfo',     0.80, ARRAY['price','aliphatic']),
    ('21cp.com',       '中塑在线 CN Plastics', 0.70, ARRAY['news','events']),
    ('stats.gov.cn',   '国家统计局 NBS',       0.95, ARRAY['demand','macro']),
    ('mee.gov.cn',     '生态环境部 MEE',       0.95, ARRAY['regulatory'])
ON CONFLICT (domain) DO NOTHING;

-- product families
INSERT INTO product_families (code, name, name_cn, description) VALUES
    ('aromatic_curing', 'Aromatic Curing Agents', '芳香族固化剂', 'TDI-based, ~60-70% of hardener SME volume'),
    ('aliphatic_curing', 'Aliphatic Curing Agents', '脂肪族固化剂', 'HDI-based, premium tier ~15-25%'),
    ('specialty_curing', 'Specialty Curing Agents', '特种固化剂', 'IPDI / blocked isocyanates, low volume / high margin'),
    ('pu_adhesive', 'PU Adhesive Prepolymers', 'PU 胶粘剂 / 预聚体', 'Optional downstream SKU')
ON CONFLICT (code) DO NOTHING;

-- finished products (10) — anchored on real spec references
INSERT INTO catalog_finished_product (family_id, code, name, name_cn, default_region_code, description) VALUES
    ((SELECT id FROM product_families WHERE code='aromatic_curing'), 'TDI_TMP_75',     'TDI-TMP Adduct 75% (BAc)', 'TDI-TMP 加成物 75%', 'CN-EC', 'Classic 75-hardener for wood coatings, leather, PU adhesives. NCO ~13%'),
    ((SELECT id FROM product_families WHERE code='aromatic_curing'), 'TDI_TRIMER_50',  'TDI Trimer (Isocyanurate) 50%', 'TDI 三聚体 50%', 'CN-EC', 'Industrial coatings, lower free-TDI variant'),
    ((SELECT id FROM product_families WHERE code='aromatic_curing'), 'TDI_BIURET',     'TDI Biuret Adduct',         'TDI 缩二脲',         'CN-EC', 'Adhesive grade'),
    ((SELECT id FROM product_families WHERE code='aromatic_curing'), 'TDI_LF_75',      'Low-free TDI Adduct 75%',   '低游离TDI 加成物',   'CN-EC', 'Free-TDI <0.5%; export/REACH grade'),
    ((SELECT id FROM product_families WHERE code='aliphatic_curing'),'HDI_TRIMER_N3300','HDI Trimer (N3300/HT100 equiv)', 'HDI 三聚体', 'CN-EC', 'NCO 21-23%, weatherable coatings'),
    ((SELECT id FROM product_families WHERE code='aliphatic_curing'),'HDI_BIURET_N75', 'HDI Biuret (N75 equiv)',    'HDI 缩二脲',         'CN-EC', 'NCO 21-23%, alternative to trimer'),
    ((SELECT id FROM product_families WHERE code='aliphatic_curing'),'HDI_WATERBORNE', 'HDI Waterborne Hardener',   'HDI 水分散型固化剂', 'CN-EC', 'For 2K waterborne PU systems'),
    ((SELECT id FROM product_families WHERE code='specialty_curing'),'IPDI_TRIMER',    'IPDI Trimer',               'IPDI 三聚体',        'CN-EC', 'High-end automotive refinish'),
    ((SELECT id FROM product_families WHERE code='specialty_curing'),'BLOCKED_ISO',    'Blocked Isocyanate (MEKO)', '封闭型固化剂',       'CN-EC', 'For powder/coil coating'),
    ((SELECT id FROM product_families WHERE code='pu_adhesive'),     'OC_MOISTURE_PU', '1K Moisture-cure PU Adhesive', '单组份湿固化PU胶', 'CN-EC', 'Footwear/construction')
ON CONFLICT (code) DO NOTHING;

-- raw materials (20)
INSERT INTO catalog_raw_material (code, name, name_cn, unit, category, volatility, supply_risk) VALUES
    ('TDI',       'Toluene Diisocyanate',           'TDI 二异氰酸酯',     'CNY/ton', 'isocyanate', 'high',   'high'),
    ('MDI',       'Methylene Diphenyl Diisocyanate','MDI',                'CNY/ton', 'isocyanate', 'high',   'high'),
    ('HDI',       'Hexamethylene Diisocyanate',     'HDI',                'CNY/ton', 'isocyanate', 'high',   'high'),
    ('IPDI',      'Isophorone Diisocyanate',        'IPDI',               'CNY/ton', 'isocyanate', 'medium', 'high'),
    ('PPG_2000',  'Polyether Polyol PPG-2000',      '聚醚多元醇 PPG-2000','CNY/ton', 'polyol',     'medium', 'low'),
    ('POLYESTER_OL','Polyester Polyol',             '聚酯多元醇',         'CNY/ton', 'polyol',     'medium', 'low'),
    ('TOLUENE',   'Toluene',                        '甲苯',               'CNY/ton', 'macro',      'high',   'low'),
    ('PHENOL',    'Phenol',                         '苯酚',               'CNY/ton', 'macro',      'high',   'low'),
    ('FORMALIN',  'Formaldehyde 37%',               '甲醛 37%',           'CNY/ton', 'macro',      'medium', 'low'),
    ('BAC',       'n-Butyl Acetate',                '醋酸丁酯',           'CNY/ton', 'solvent',    'high',   'low'),
    ('PMA',       'Propylene Glycol Methyl Ether Acetate', 'PMA 醋酸酯', 'CNY/ton', 'solvent',    'medium', 'low'),
    ('TMP',       'Trimethylolpropane',             'TMP 三羟甲基丙烷',   'CNY/ton', 'additive',   'medium', 'low'),
    ('DEG',       'Diethylene Glycol',              'DEG 二甘醇',         'CNY/ton', 'additive',   'medium', 'low'),
    ('MEG',       'Monoethylene Glycol',            'MEG 乙二醇',         'CNY/ton', 'additive',   'medium', 'low'),
    ('DBTDL',     'Dibutyltin Dilaurate',           'DBTDL 二月桂酸二丁基锡', 'CNY/ton', 'catalyst', 'high', 'medium'),
    ('AMINE_CAT', 'Tertiary Amine Catalyst',        '叔胺催化剂',         'CNY/ton', 'catalyst',   'medium', 'low'),
    ('BHT',       'Butylated Hydroxytoluene (stabilizer)', 'BHT 抗氧剂', 'CNY/ton', 'additive',   'low',    'low'),
    ('DMC_CAT',   'DMC (Double Metal Cyanide) Catalyst', 'DMC 催化剂',  'CNY/ton', 'catalyst',   'low',    'medium'),
    ('BRENT',     'Brent Crude',                    '布伦特原油',         'USD/bbl', 'macro',      'high',   'low'),
    ('CNY_USD',   'CNY/USD FX',                     '人民币兑美元',       'CNY/USD', 'macro',      'low',    'low')
ON CONFLICT (code) DO NOTHING;

-- BoM links (concise, only the critical ones; tenants can add detail)
INSERT INTO catalog_bom (finished_product_id, raw_material_id, pct_of_cost, is_critical, notes) VALUES
    ((SELECT id FROM catalog_finished_product WHERE code='TDI_TMP_75'), (SELECT id FROM catalog_raw_material WHERE code='TDI'),     65, true,  '~65% of variable cost'),
    ((SELECT id FROM catalog_finished_product WHERE code='TDI_TMP_75'), (SELECT id FROM catalog_raw_material WHERE code='TMP'),     10, false, NULL),
    ((SELECT id FROM catalog_finished_product WHERE code='TDI_TMP_75'), (SELECT id FROM catalog_raw_material WHERE code='BAC'),     20, false, NULL),
    ((SELECT id FROM catalog_finished_product WHERE code='HDI_TRIMER_N3300'), (SELECT id FROM catalog_raw_material WHERE code='HDI'),         70, true, NULL),
    ((SELECT id FROM catalog_finished_product WHERE code='HDI_TRIMER_N3300'), (SELECT id FROM catalog_raw_material WHERE code='BAC'),         15, false, NULL),
    ((SELECT id FROM catalog_finished_product WHERE code='HDI_TRIMER_N3300'), (SELECT id FROM catalog_raw_material WHERE code='DBTDL'),       3,  true,  'Catalyst, REACH watch'),
    ((SELECT id FROM catalog_finished_product WHERE code='IPDI_TRIMER'),     (SELECT id FROM catalog_raw_material WHERE code='IPDI'),        70, true,  'Near-monopoly supply'),
    ((SELECT id FROM catalog_finished_product WHERE code='OC_MOISTURE_PU'),  (SELECT id FROM catalog_raw_material WHERE code='TDI'),         40, true,  NULL),
    ((SELECT id FROM catalog_finished_product WHERE code='OC_MOISTURE_PU'),  (SELECT id FROM catalog_raw_material WHERE code='PPG_2000'),    35, true,  NULL)
ON CONFLICT (finished_product_id, raw_material_id) DO NOTHING;

-- indicator templates (~30)
-- Helper macro: source_id resolves by domain
INSERT INTO catalog_indicator_template (code, kind, subject_kind, subject_code, region_code, unit, cadence_minutes, source_id, formula_json, description) VALUES
    -- 6 spot price (price/raw_material) per region
    ('TDI_SPOT_EC',   'price', 'raw_material', 'TDI', 'CN-EC', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='100ppi.com'),  NULL, 'TDI East China spot'),
    ('TDI_SPOT_NC',   'price', 'raw_material', 'TDI', 'CN-NC', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='100ppi.com'),  NULL, 'TDI North China spot'),
    ('MDI_SPOT_EC',   'price', 'raw_material', 'MDI', 'CN-EC', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='100ppi.com'),  NULL, 'MDI aggregate East China'),
    ('HDI_SPOT_CN',   'price', 'raw_material', 'HDI', 'CN',    'CNY/ton', 10080, (SELECT id FROM sources WHERE domain='baiinfo.com'),NULL, 'HDI weekly (subscription source)'),
    ('IPDI_SPOT_CN',  'price', 'raw_material', 'IPDI','CN',    'CNY/ton', 10080, (SELECT id FROM sources WHERE domain='baiinfo.com'),NULL, 'IPDI weekly'),
    ('TOLUENE_SPOT',  'price', 'raw_material', 'TOLUENE','CN', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='sci99.com'),   NULL, 'Toluene spot'),
    -- macro / FX / energy
    ('PHENOL_SPOT',   'price', 'raw_material', 'PHENOL', 'CN', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='sci99.com'),   NULL, 'Phenol spot'),
    ('PPG2000_SPOT',  'price', 'raw_material', 'PPG_2000','CN','CNY/ton', 1440, (SELECT id FROM sources WHERE domain='sci99.com'),   NULL, 'PPG-2000 polyol spot'),
    ('BAC_SPOT',      'price', 'raw_material', 'BAC',    'CN', 'CNY/ton', 1440, (SELECT id FROM sources WHERE domain='100ppi.com'),  NULL, 'n-Butyl Acetate spot'),
    ('DBTDL_SPOT',    'price', 'raw_material', 'DBTDL',  'CN', 'CNY/ton', 10080, (SELECT id FROM sources WHERE domain='baiinfo.com'),NULL, 'DBTDL tin catalyst weekly'),
    ('BRENT_SPOT',    'macro', 'macro_series', 'BRENT',  'GLOBAL','USD/bbl', 1440, NULL, NULL, 'Brent crude'),
    ('CNY_USD_SPOT',  'macro', 'macro_series', 'CNY_USD','GLOBAL','CNY/USD', 1440, NULL, NULL, 'CNY/USD mid-rate'),
    -- composite spreads (formula_json = {op, left, right})
    ('TDI_TOLUENE_SPREAD', 'spread', 'raw_material', 'TDI', 'CN-EC', 'CNY/ton', 1440, NULL,
        '{"op":"subtract","left":{"indicator_code":"TDI_SPOT_EC"},"right":{"indicator_code":"TOLUENE_SPOT"}}'::jsonb,
        'Producer margin proxy: TDI minus toluene'),
    ('MDI_TDI_SPREAD',     'spread', 'raw_material', 'MDI', 'CN-EC', 'CNY/ton', 1440, NULL,
        '{"op":"subtract","left":{"indicator_code":"MDI_SPOT_EC"},"right":{"indicator_code":"TDI_SPOT_EC"}}'::jsonb,
        'MDI vs TDI substitution signal'),
    ('HDI_TDI_RATIO',      'derived', 'raw_material', 'HDI', 'CN', 'ratio', 10080, NULL,
        '{"op":"divide","left":{"indicator_code":"HDI_SPOT_CN"},"right":{"indicator_code":"TDI_SPOT_EC"}}'::jsonb,
        'Aliphatic premium ratio'),
    -- demand
    ('CN_CONSTRUCTION_PMI','demand', 'macro_series', 'CONSTRUCTION_PMI', 'CN', 'index', 43200, (SELECT id FROM sources WHERE domain='stats.gov.cn'), NULL, 'NBS construction PMI, monthly'),
    ('CN_AUTO_PROD',       'demand', 'macro_series', 'AUTO_PROD',        'CN', 'units/mo', 43200, (SELECT id FROM sources WHERE domain='stats.gov.cn'), NULL, 'CAAM monthly auto production (proxy via NBS)'),
    ('CN_FURNITURE_EXPORT','demand', 'macro_series', 'FURNITURE_EXP',    'CN', 'USD/mo', 43200, (SELECT id FROM sources WHERE domain='stats.gov.cn'), NULL, 'Furniture exports — drives wood-coating TDI demand'),
    ('CN_FOOTWEAR_EXPORT', 'demand', 'macro_series', 'FOOTWEAR_EXP',     'CN', 'USD/mo', 43200, (SELECT id FROM sources WHERE domain='stats.gov.cn'), NULL, 'Footwear exports — drives PU-adhesive demand'),
    ('BAIDU_TDI',          'demand', 'macro_series', 'BAIDU_TDI',        'CN', 'index', 10080, NULL, NULL, 'Baidu Index search interest for "TDI"'),
    ('BAIDU_PU_HARDENER',  'demand', 'macro_series', 'BAIDU_PUH',        'CN', 'index', 10080, NULL, NULL, 'Baidu Index for "聚氨酯固化剂"'),
    -- supply / events
    ('WANHUA_FUJIAN_STATUS','supply', 'raw_material', 'TDI', 'CN', 'state', 1440, (SELECT id FROM sources WHERE domain='oilchem.net'), NULL, 'Wanhua Fujian Phase 1 operational status'),
    ('COVESTRO_SH_STATUS', 'supply', 'raw_material', 'MDI', 'CN', 'state', 1440, (SELECT id FROM sources WHERE domain='oilchem.net'), NULL, 'Covestro Shanghai status'),
    ('VENCOREX_STATUS',    'supply', 'raw_material', 'HDI', 'GLOBAL','state', 10080, (SELECT id FROM sources WHERE domain='21cp.com'), NULL, 'Vencorex post-2025 restructuring status'),
    ('MAINTENANCE_TDI_QTR','supply', 'raw_material', 'TDI', 'CN', 'kt_offline', 10080, (SELECT id FROM sources WHERE domain='oilchem.net'), NULL, 'Aggregate TDI capacity offline (rolling quarter)'),
    -- regulatory
    ('SHANDONG_VOC_POLICY','regulatory', 'region', 'CN-EC', 'CN-EC','event', 43200, (SELECT id FROM sources WHERE domain='mee.gov.cn'), NULL, 'Shandong VOC enforcement events'),
    ('JIANGSU_CHEM_PARK',  'regulatory', 'region', 'CN-EC', 'CN-EC','event', 43200, (SELECT id FROM sources WHERE domain='mee.gov.cn'), NULL, 'Jiangsu chemical park access policy'),
    ('CHEM_SAFETY_2024_2026','regulatory', 'region','CN',   'CN',   'event', 43200, (SELECT id FROM sources WHERE domain='mee.gov.cn'), NULL, 'Old-plant safety retrofit deadline'),
    ('REACH_FREE_TDI',     'regulatory', 'raw_material','TDI','GLOBAL','event', 43200, NULL, NULL, 'REACH free-TDI restriction updates'),
    ('IMPORT_PARITY_TDI',  'derived', 'raw_material','TDI','CN','CNY/ton', 1440, NULL,
        '{"op":"add","left":{"indicator_code":"TDI_SPOT_EC"},"right":{"indicator_code":"CNY_USD_SPOT","scalar":0}}'::jsonb,
        'Placeholder for import-parity computation; v2 wires Korea/Japan CIF feeds')
ON CONFLICT (code) DO NOTHING;
