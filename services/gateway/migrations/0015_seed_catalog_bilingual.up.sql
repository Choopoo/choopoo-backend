-- Backfill bilingual content for catalog_indicator_template,
-- catalog_signal_aspect, and sources. The owner is a Chinese PU SME so
-- the Chinese strings are the primary user-facing label; English stays
-- around for the bilingual deploy + reviewers.
--
-- Tone: plain prose, what-it-means-for-procurement framing.
-- No engineering placeholders, no acronym soup without explanation.

-- ─────────────── INDICATORS ───────────────

UPDATE catalog_indicator_template SET
    name = 'TDI Spot · East China',
    name_cn = 'TDI 现货 · 华东',
    description = 'TDI East China spot reference — primary procurement benchmark.',
    description_cn = 'TDI 华东现货价 — 主要的采购参考基准。'
WHERE code = 'TDI_SPOT_EC';

UPDATE catalog_indicator_template SET
    name = 'TDI Spot · North China',
    name_cn = 'TDI 现货 · 华北',
    description = 'TDI North China spot — north-vs-east arb watch.',
    description_cn = 'TDI 华北现货 — 用于观察南北价差套利。'
WHERE code = 'TDI_SPOT_NC';

UPDATE catalog_indicator_template SET
    name = 'MDI Aggregate · East China',
    name_cn = 'MDI 综合价 · 华东',
    description = 'Aggregate MDI spot for East China — substitution signal vs TDI.',
    description_cn = 'MDI 华东综合现货 — 与 TDI 的替代关系信号。'
WHERE code = 'MDI_SPOT_EC';

UPDATE catalog_indicator_template SET
    name = 'HDI Spot · China',
    name_cn = 'HDI 现货 · 全国',
    description = 'HDI weekly subscription source — aliphatic premium tracking.',
    description_cn = 'HDI 周度订阅价 — 用于跟踪脂肪族溢价。'
WHERE code = 'HDI_SPOT_CN';

UPDATE catalog_indicator_template SET
    name = 'IPDI Spot · China',
    name_cn = 'IPDI 现货 · 全国',
    description = 'IPDI weekly — niche aliphatic, low-volume.',
    description_cn = 'IPDI 周度报价 — 小众脂肪族，量少。'
WHERE code = 'IPDI_SPOT_CN';

UPDATE catalog_indicator_template SET
    name = 'Toluene Spot',
    name_cn = '甲苯现货',
    description = 'Toluene spot — TDI feedstock cost driver.',
    description_cn = '甲苯现货价 — TDI 上游原料成本主因。'
WHERE code = 'TOLUENE_SPOT';

UPDATE catalog_indicator_template SET
    name = 'Phenol Spot',
    name_cn = '苯酚现货',
    description = 'Phenol spot — MDI feedstock cost driver.',
    description_cn = '苯酚现货价 — MDI 上游原料成本主因。'
WHERE code = 'PHENOL_SPOT';

UPDATE catalog_indicator_template SET
    name = 'PPG-2000 Polyol Spot',
    name_cn = 'PPG-2000 聚醚现货',
    description = 'PPG-2000 polyol spot — paired with isocyanate to make PU foam/elastomer.',
    description_cn = 'PPG-2000 聚醚现货 — 与异氰酸酯配比制备聚氨酯泡沫/弹性体。'
WHERE code = 'PPG2000_SPOT';

UPDATE catalog_indicator_template SET
    name = 'n-Butyl Acetate Spot',
    name_cn = '醋酸正丁酯现货',
    description = 'BAC spot — common PU coating solvent.',
    description_cn = '醋酸正丁酯现货 — 聚氨酯涂料常用溶剂。'
WHERE code = 'BAC_SPOT';

UPDATE catalog_indicator_template SET
    name = 'DBTDL Tin Catalyst',
    name_cn = 'DBTDL 锡催化剂',
    description = 'Dibutyltin dilaurate weekly — common PU cure catalyst.',
    description_cn = '二月桂酸二丁基锡周度价 — 聚氨酯固化常用催化剂。'
WHERE code = 'DBTDL_SPOT';

UPDATE catalog_indicator_template SET
    name = 'Brent Crude',
    name_cn = '布伦特原油',
    description = 'Brent crude — global oil benchmark; flows through to feedstocks.',
    description_cn = '布伦特原油 — 全球油价基准，传导至化工原料。'
WHERE code = 'BRENT_SPOT';

UPDATE catalog_indicator_template SET
    name = 'CNY/USD Mid-Rate',
    name_cn = '人民币兑美元中间价',
    description = 'PBOC daily mid-rate — drives import-parity math.',
    description_cn = '央行人民币兑美元日中间价 — 决定进口平价计算。'
WHERE code = 'CNY_USD_SPOT';

UPDATE catalog_indicator_template SET
    name = 'TDI − Toluene Spread',
    name_cn = 'TDI 与甲苯价差',
    description = 'Producer margin proxy: TDI spot minus toluene cost.',
    description_cn = '生产端毛利代理：TDI 现货价减去甲苯成本。'
WHERE code = 'TDI_TOLUENE_SPREAD';

UPDATE catalog_indicator_template SET
    name = 'MDI / TDI Substitution',
    name_cn = 'MDI 与 TDI 替代信号',
    description = 'MDI / TDI ratio — when one runs hot, formulators switch.',
    description_cn = 'MDI 对 TDI 比值 — 一方走高时配方师会切换。'
WHERE code = 'MDI_TDI_SPREAD';

UPDATE catalog_indicator_template SET
    name = 'HDI / TDI Premium',
    name_cn = 'HDI 对 TDI 溢价',
    description = 'Aliphatic premium ratio — health of the high-end coating market.',
    description_cn = '脂肪族溢价比 — 反映高端涂料市场冷热。'
WHERE code = 'HDI_TDI_RATIO';

UPDATE catalog_indicator_template SET
    name = 'Construction PMI',
    name_cn = '建筑业 PMI',
    description = 'NBS construction PMI, monthly — leading indicator for PU rigid-foam demand.',
    description_cn = '国家统计局建筑业 PMI 月度数据 — PU 硬泡需求先行指标。'
WHERE code = 'CN_CONSTRUCTION_PMI';

UPDATE catalog_indicator_template SET
    name = 'Auto Production · China',
    name_cn = '汽车产量 · 全国',
    description = 'CAAM monthly auto output — PU seat-foam + coating demand proxy.',
    description_cn = '中国汽车工业协会月度汽车产量 — PU 座椅泡沫+涂料需求代理。'
WHERE code = 'CN_AUTO_PROD';

UPDATE catalog_indicator_template SET
    name = 'Furniture Exports',
    name_cn = '家具出口',
    description = 'Furniture exports — drives wood-coating TDI demand.',
    description_cn = '家具出口数据 — 拉动木器涂料 TDI 需求。'
WHERE code = 'CN_FURNITURE_EXPORT';

UPDATE catalog_indicator_template SET
    name = 'Footwear Exports',
    name_cn = '鞋类出口',
    description = 'Footwear exports — drives PU-adhesive demand.',
    description_cn = '鞋类出口数据 — 拉动 PU 胶粘剂需求。'
WHERE code = 'CN_FOOTWEAR_EXPORT';

UPDATE catalog_indicator_template SET
    name = 'Baidu Index · TDI',
    name_cn = '百度指数 · TDI',
    description = 'Baidu Index search interest for "TDI" — early demand sentiment.',
    description_cn = '"TDI" 百度指数搜索热度 — 需求情绪早期信号。'
WHERE code = 'BAIDU_TDI';

UPDATE catalog_indicator_template SET
    name = 'Baidu Index · PU Hardener',
    name_cn = '百度指数 · 聚氨酯固化剂',
    description = 'Baidu Index for "聚氨酯固化剂" — downstream formulator interest.',
    description_cn = '"聚氨酯固化剂" 百度指数 — 下游配方师关注度。'
WHERE code = 'BAIDU_PU_HARDENER';

UPDATE catalog_indicator_template SET
    name = 'Wanhua Fujian Phase 1',
    name_cn = '万华福建一期',
    description = 'Wanhua Fujian Phase 1 operational status — major MDI capacity.',
    description_cn = '万华福建一期装置运营状态 — 主要 MDI 产能。'
WHERE code = 'WANHUA_FUJIAN_STATUS';

UPDATE catalog_indicator_template SET
    name = 'Covestro Shanghai',
    name_cn = '科思创上海',
    description = 'Covestro Shanghai status — major TDI/MDI producer.',
    description_cn = '科思创上海装置状态 — 主要 TDI/MDI 生产商。'
WHERE code = 'COVESTRO_SH_STATUS';

UPDATE catalog_indicator_template SET
    name = 'Vencorex',
    name_cn = '万可凯',
    description = 'Vencorex post-2025 restructuring status — HDI supply-side risk.',
    description_cn = '万可凯 2025 后重组状态 — HDI 供应端风险。'
WHERE code = 'VENCOREX_STATUS';

UPDATE catalog_indicator_template SET
    name = 'TDI Maintenance · Quarter',
    name_cn = 'TDI 装置检修 · 季度',
    description = 'Aggregate TDI capacity offline (rolling quarter) — supply-tightness gauge.',
    description_cn = '季度滚动 TDI 装置停产产能合计 — 供应紧张程度指标。'
WHERE code = 'MAINTENANCE_TDI_QTR';

UPDATE catalog_indicator_template SET
    name = 'Shandong VOC Policy',
    name_cn = '山东 VOC 政策',
    description = 'Shandong VOC enforcement events — solvent-coating demand swings.',
    description_cn = '山东 VOC 执法事件 — 溶剂型涂料需求波动。'
WHERE code = 'SHANDONG_VOC_POLICY';

UPDATE catalog_indicator_template SET
    name = 'Jiangsu Chemical Park Policy',
    name_cn = '江苏化工园区政策',
    description = 'Jiangsu chemical park access policy — affects upstream supply siting.',
    description_cn = '江苏化工园区准入政策 — 影响上游供应布局。'
WHERE code = 'JIANGSU_CHEM_PARK';

UPDATE catalog_indicator_template SET
    name = 'Old-Plant Safety Retrofit Deadline',
    name_cn = '老旧装置安全改造截止',
    description = 'Old-plant safety retrofit deadline (2024–2026) — forces capacity offline.',
    description_cn = '老旧装置安全改造截止期（2024–2026）— 推动产能下线。'
WHERE code = 'CHEM_SAFETY_2024_2026';

UPDATE catalog_indicator_template SET
    name = 'EU REACH · Free TDI',
    name_cn = '欧盟 REACH · 游离 TDI',
    description = 'REACH free-TDI restriction updates — affects export-bound formulations.',
    description_cn = '欧盟 REACH 游离 TDI 限制更新 — 影响出口配方。'
WHERE code = 'REACH_FREE_TDI';

UPDATE catalog_indicator_template SET
    name = 'TDI Import Parity',
    name_cn = 'TDI 进口平价',
    description = 'Cost to import TDI vs domestic spot — flips with CNY weakness or Korea/Japan ramp-ups.',
    description_cn = '进口 TDI 与国内现货成本对比 — 人民币贬值或韩日增产时翻转。'
WHERE code = 'IMPORT_PARITY_TDI';

-- ─────────────── ASPECTS ───────────────

UPDATE catalog_signal_aspect SET
    name_cn = '价格 · 现货/合约/期货',
    description_cn = '跨交易所与门户聚合的直接价格行情。'
WHERE code = 'price';

UPDATE catalog_signal_aspect SET
    name_cn = '装置事件 · 检修/不可抗力',
    description_cn = '生产商装置的计划停产、不可抗力、事故。'
WHERE code = 'supply_event';

UPDATE catalog_signal_aspect SET
    name_cn = '航运与物流',
    description_cn = '上海集装箱运价指数、红海事件、港口拥堵。'
WHERE code = 'shipping';

UPDATE catalog_signal_aspect SET
    name_cn = '政策与合规',
    description_cn = 'REACH、化工安全、VOC、关税。'
WHERE code = 'regulatory';

UPDATE catalog_signal_aspect SET
    name_cn = '台风/寒潮/干旱',
    description_cn = '触发港口关闭或装置停产的登陆事件。'
WHERE code = 'weather';

UPDATE catalog_signal_aspect SET
    name_cn = '海关进出口',
    description_cn = '海关 / 美国 Census 月度 HS 编码流量。'
WHERE code = 'trade_flow';

UPDATE catalog_signal_aspect SET
    name_cn = '冲突与制裁',
    description_cn = 'GDELT 主题、ACLED 事件、制裁裁决。'
WHERE code = 'geopolitics';

UPDATE catalog_signal_aspect SET
    name_cn = '下游需求代理',
    description_cn = '建筑业 PMI、汽车产量、家具出口。'
WHERE code = 'demand_proxy';

UPDATE catalog_signal_aspect SET
    name_cn = '产能新增/退出',
    description_cn = '装置扩建、延期、关停的公告。'
WHERE code = 'capacity_news';

UPDATE catalog_signal_aspect SET
    name_cn = '宏观与汇率',
    description_cn = '布伦特原油、人民币/美元、上海银行间拆放利率。'
WHERE code = 'macro_fx';

-- ─────────────── SOURCES ───────────────
-- Split the bilingual blob into clean (English label, Chinese label_cn).

UPDATE sources SET label = 'Sunsirs',     label_cn = '生意社'   WHERE label = '生意社 Sunsirs';
UPDATE sources SET label = 'Sublime',     label_cn = '卓创资讯' WHERE label = '卓创资讯 Sublime';
UPDATE sources SET label = 'Longzhong',   label_cn = '隆众资讯' WHERE label = '隆众资讯 Longzhong';
UPDATE sources SET label = 'Baiinfo',     label_cn = '百川盈孚' WHERE label = '百川盈孚 Baiinfo';
UPDATE sources SET label = 'CN Plastics', label_cn = '中塑在线' WHERE label = '中塑在线 CN Plastics';
UPDATE sources SET label = 'NBS',         label_cn = '国家统计局' WHERE label = '国家统计局 NBS';
UPDATE sources SET label = 'MEE',         label_cn = '生态环境部' WHERE label = '生态环境部 MEE';
