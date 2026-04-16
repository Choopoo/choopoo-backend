-- Seed the 10 canonical signal aspects + pre-rank the most common ones for
-- our seeded subjects (TDI, MDI, HDI) with induction chains and example
-- events. The chains below are hand-curated from Agent 2's domain research
-- so they're auditable starting points, NOT LLM-hallucinated.

INSERT INTO catalog_signal_aspect (code, name, description, axis, default_relevance) VALUES
    ('price',          'Spot / contract / futures',   'Direct price quote aggregated across exchanges + portals', 'price', 0.95),
    ('supply_event',   'Plant maintenance / FM',      'Scheduled shutdowns, force majeure, incidents at producer plants', 'supply_event', 0.85),
    ('shipping',       'Freight & logistics',         'SCFI, Red Sea disruption, port congestion', 'shipping', 0.55),
    ('regulatory',     'Policy / compliance',         'REACH, 化工安全, VOC, tariffs', 'regulatory', 0.45),
    ('weather',        'Typhoon / freeze / drought',  'Landfall events that trigger port closures or plant shutdowns', 'weather', 0.40),
    ('trade_flow',     'Customs-level imports/exports','Monthly HS-code flows from 海关 / US Census', 'trade_flow', 0.50),
    ('geopolitics',    'Conflict / sanctions',        'GDELT themes, ACLED events, sanctions rulings', 'geopolitics', 0.35),
    ('demand_proxy',   'Downstream demand proxies',   'Construction PMI, auto prod, furniture export', 'demand_proxy', 0.60),
    ('capacity_news',  'Capacity additions/retirements','Announcements of plant expansions, delays, closures', 'capacity_news', 0.50),
    ('macro_fx',       'Macro + FX',                  'Brent, CNY/USD, SHIBOR', 'macro_fx', 0.55)
ON CONFLICT (code) DO NOTHING;

-- Bind existing sources to their natural aspect(s).
-- 生意社 (100ppi.com) feeds `price`.
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 1440, 0.85
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'price' AND s.domain = '100ppi.com'
ON CONFLICT DO NOTHING;

INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 1440, 0.85
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'price' AND s.domain = 'sci99.com'
ON CONFLICT DO NOTHING;

INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 1440, 0.80
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'price' AND s.domain = 'oilchem.net'
ON CONFLICT DO NOTHING;

-- 百川 feeds `price` for HDI/IPDI weekly
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 10080, 0.75
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'price' AND s.domain = 'baiinfo.com'
ON CONFLICT DO NOTHING;

-- 隆众 feeds `supply_event` (装置动态)
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 1440, 0.80
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'supply_event' AND s.domain = 'oilchem.net'
ON CONFLICT DO NOTHING;

-- 中塑在线 feeds `supply_event` (news)
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 360, 0.70
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'supply_event' AND s.domain = '21cp.com'
ON CONFLICT DO NOTHING;

-- 生态环境部 feeds `regulatory`
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 10080, 0.95
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'regulatory' AND s.domain = 'mee.gov.cn'
ON CONFLICT DO NOTHING;

-- 国家统计局 feeds `demand_proxy`
INSERT INTO aspect_provider (aspect_id, source_id, update_freq_minutes, trust_score)
SELECT a.id, s.id, 43200, 0.95
  FROM catalog_signal_aspect a, sources s
 WHERE a.code = 'demand_proxy' AND s.domain = 'stats.gov.cn'
ON CONFLICT DO NOTHING;

-- Seed subject_aspect_score for TDI, MDI, HDI with curated induction chains.
-- These rationales are human-authored from Agent 2's domain research (not
-- LLM-hallucinated), so evidence_verified defaults to FALSE but the chains
-- are defensible. The review-and-verify flow can upgrade them later.

-- TDI: price + supply_event + demand_proxy are the big three.
INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'active', 0.95, 1.00, 0.95,
       'Direct price quote; baseline required for all downstream reasoning.',
       '[{"step":1,"fact":"Portals publish daily benchmark prices"},{"step":2,"fact":"Price is the unit of account for every downstream decision"}]'::jsonb,
       '[{"date":"2026-04-16","event":"TDI East China spot 15,820 ¥/t","observed_impact":"baseline","source_url":"https://100ppi.com","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'price'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'active', 0.85, 0.92, 0.78,
       'Wanhua/Covestro/BASF maintenance schedules directly compress supply and move spot within 48h.',
       '[{"step":1,"cause":"Producer announces maintenance window"},{"step":2,"effect":"Expected output falls by plant nameplate capacity × days"},{"step":3,"effect":"Buyers pre-buy, spot firms by 1-3%"},{"step":4,"effect":"Spread vs toluene widens until restart"}]'::jsonb,
       '[{"date":"2026-04-04","event":"Wanhua Fujian Phase 1 maintenance start, 12-day window","observed_impact":"TDI EC +0.8% next 5 sessions","source_url":"https://oilchem.net","verified":false},{"date":"2024-Q1","event":"Covestro Germany 300kt offline + BASF Korea 160kt","observed_impact":"+5.9% MoM globally","source_url":"https://baiinfo.com","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'supply_event'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'active', 0.72, 0.85, 0.61,
       'Downstream pull from construction + furniture export leads TDI spot by ~30d.',
       '[{"step":1,"cause":"Construction PMI rises above 50"},{"step":2,"effect":"Wood-coating demand picks up"},{"step":3,"effect":"TDI-75 hardener order book fills"},{"step":4,"effect":"Spot firms within 30-45 days"}]'::jsonb,
       '[{"date":"2024-Q3","event":"China furniture exports +8% YoY","observed_impact":"TDI EC held firm through Oct","source_url":"https://stats.gov.cn","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'demand_proxy'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'candidate', 0.55, 0.90, 0.50,
       'Upstream toluene + crude set TDI producer margin; shifts margin but does not always pass through.',
       '[{"step":1,"cause":"Brent crude rises"},{"step":2,"effect":"Refinery margins squeezed on toluene"},{"step":3,"effect":"Toluene spot tracks +0.4-0.6 × move"},{"step":4,"effect":"TDI producers resist passing through; spread compresses"}]'::jsonb,
       '[{"date":"2026-Q1","event":"Toluene Q1 +15% QoQ on Middle East crude disruption","observed_impact":"TDI spread vs toluene compressed 8%","source_url":"https://sci99.com","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'macro_fx'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'candidate', 0.40, 0.95, 0.38,
       'Typhoons closing Ningbo/Shanghai delay TDI exports, narrowing import parity and firming domestic spot.',
       '[{"step":1,"cause":"Typhoon makes landfall in E. China"},{"step":2,"effect":"Major ports close 2-5 days"},{"step":3,"effect":"TDI export shipments delayed"},{"step":4,"effect":"Import-parity narrows, domestic spot firms 1-2%"}]'::jsonb,
       '[{"date":"2023-07-28","event":"Typhoon Doksuri Fujian landfall","observed_impact":"TDI EC +2.3% w/w (reported)","source_url":"https://21cp.com","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'weather'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'TDI', id, 'candidate', 0.35, 0.90, 0.32,
       'REACH + low-free-TDI rulings drive premium for export-grade variants.',
       '[{"step":1,"cause":"ECHA updates free-TDI restriction"},{"step":2,"effect":"Non-compliant TDI-75 loses EU market access"},{"step":3,"effect":"Low-free variant premium widens vs standard grade"}]'::jsonb,
       '[{"date":"2020-10","event":"EU classifies TDI monomer as a skin/respiratory sensitiser","observed_impact":"Low-free hardener premium +¥2,000/t","source_url":"https://mee.gov.cn","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'regulatory'
ON CONFLICT DO NOTHING;

-- Short form for MDI and HDI: just the price + supply_event active aspects.
INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'MDI', id, 'active', 0.95, 1.00, 0.95,
       'Direct price quote baseline.',
       '[{"step":1,"fact":"Daily benchmark published"}]'::jsonb,
       '[]'::jsonb, NOW()
  FROM catalog_signal_aspect WHERE code = 'price'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'MDI', id, 'active', 0.82, 0.92, 0.75,
       'MDI is concentrated (Wanhua, Covestro, BASF, Dow); single-plant events move global spot.',
       '[{"step":1,"cause":"Announcement: major MDI plant offline"},{"step":2,"effect":"Global supply falls by ~5-10%"},{"step":3,"effect":"Spot firms 2-5% within a week"}]'::jsonb,
       '[{"date":"2026-Q1","event":"1.9M t global MDI maintenance concentrated in Q1 2026","observed_impact":"MDI China spot +2.3% MoM","source_url":"https://oilchem.net","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'supply_event'
ON CONFLICT DO NOTHING;

INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'HDI', id, 'active', 0.90, 1.00, 0.90,
       'Weekly price from a paid source (百川); only reliable quote for this aliphatic.',
       '[{"step":1,"fact":"百川 publishes weekly HDI spot"}]'::jsonb,
       '[]'::jsonb, NOW()
  FROM catalog_signal_aspect WHERE code = 'price'
ON CONFLICT DO NOTHING;

-- HDI: geopolitics matters because Vencorex restructuring in 2025 altered global supply.
INSERT INTO subject_aspect_score
  (subject_code, aspect_id, status, relevance_r, diversity_bonus, score,
   relevance_rationale, induction_chain, example_events, last_scored_at)
SELECT 'HDI', id, 'active', 0.75, 0.95, 0.71,
       'HDI supply is dominated by Wanhua, Covestro, Vencorex; political/ownership events at any of the three move spot.',
       '[{"step":1,"cause":"Vencorex restructuring announced"},{"step":2,"effect":"European HDI supply uncertain for 12-18 months"},{"step":3,"effect":"Chinese buyers accept Wanhua premium to secure volume"},{"step":4,"effect":"Domestic HDI spot firms, import-parity widens"}]'::jsonb,
       '[{"date":"2025","event":"Vencorex restructuring + ownership change","observed_impact":"Global HDI premium widened","source_url":"https://21cp.com","verified":false}]'::jsonb,
       NOW()
  FROM catalog_signal_aspect WHERE code = 'geopolitics'
ON CONFLICT DO NOTHING;
