-- KR Apartment Market AI Skill
-- Idempotent baseline registry and metric seeds
-- Requires database/schema.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- Sources
-- ---------------------------------------------------------------------------

INSERT INTO ref.data_source (
  source_id, source_code, display_name, owner_name, source_category, access_mode,
  base_url, allowed_hosts, license_name, terms_url, attribution_template,
  can_ingest, can_cache, can_redistribute, can_derive, enabled, metadata
)
VALUES
  (
    '10000000-0000-4000-8000-000000000001',
    'molit_public',
    '국토교통부 공공 실거래 API',
    '국토교통부',
    'PUBLIC_API',
    'PUBLIC_OPEN',
    'https://apis.data.go.kr/',
    ARRAY['apis.data.go.kr'],
    '공공데이터포털 이용허락범위 제한 없음',
    'https://www.data.go.kr/data/15126469/openapi.do',
    '출처: 국토교통부 공공 실거래 API',
    true, true, true, true, true,
    '{"service_key_required":true,"credential_storage":"secret_manager_only"}'::jsonb
  ),
  (
    '10000000-0000-4000-8000-000000000002',
    'molit_rt',
    '국토교통부 실거래가 공개시스템',
    '국토교통부',
    'PUBLIC_SITE',
    'LINK_OUT_ONLY',
    'https://rt.molit.go.kr/',
    ARRAY['rt.molit.go.kr'],
    NULL,
    'https://rt.molit.go.kr/',
    '국토교통부 실거래가 공개시스템에서 원문 확인',
    false, false, false, false, true,
    '{"purpose":"verified_link_out"}'::jsonb
  ),
  (
    '10000000-0000-4000-8000-000000000003',
    'data_go_kr',
    '공공데이터포털',
    '행정안전부·한국지능정보사회진흥원',
    'PUBLIC_SITE',
    'LINK_OUT_ONLY',
    'https://www.data.go.kr/',
    ARRAY['www.data.go.kr'],
    NULL,
    'https://www.data.go.kr/',
    '공공데이터포털에서 API 명세 확인',
    false, false, false, false, true,
    '{"purpose":"dataset_documentation_link"}'::jsonb
  ),
  (
    '10000000-0000-4000-8000-000000000004',
    'apt2me',
    '아파트Me',
    NULL,
    'LINK_OUT',
    'LINK_OUT_ONLY',
    'https://apt2.me/',
    ARRAY['apt2.me'],
    NULL,
    'https://apt2.me/',
    '아파트Me에서 원문 확인',
    false, false, false, false, true,
    '{"authorization_status":"not_granted","content_ingestion":false,"note":"Written authorization is required before any automated ingestion."}'::jsonb
  )
ON CONFLICT (source_code) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  owner_name = EXCLUDED.owner_name,
  source_category = EXCLUDED.source_category,
  access_mode = EXCLUDED.access_mode,
  base_url = EXCLUDED.base_url,
  allowed_hosts = EXCLUDED.allowed_hosts,
  license_name = EXCLUDED.license_name,
  terms_url = EXCLUDED.terms_url,
  attribution_template = EXCLUDED.attribution_template,
  can_ingest = EXCLUDED.can_ingest,
  can_cache = EXCLUDED.can_cache,
  can_redistribute = EXCLUDED.can_redistribute,
  can_derive = EXCLUDED.can_derive,
  enabled = EXCLUDED.enabled,
  metadata = EXCLUDED.metadata;

-- ---------------------------------------------------------------------------
-- Datasets
-- ---------------------------------------------------------------------------

INSERT INTO ref.dataset (
  dataset_id, source_id, dataset_code, display_name, property_type, trade_type,
  endpoint_template, api_version, response_format, timezone,
  freshness_sla_minutes, supports_cancellations, enabled, metadata
)
VALUES
  (
    '20000000-0000-4000-8000-000000000001',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'molit_public'),
    'MOLIT_APT_SALE',
    '국토교통부 아파트 매매 실거래',
    'APARTMENT',
    'SALE',
    NULL,
    '2026-07',
    'XML',
    'Asia/Seoul',
    1440,
    true,
    true,
    '{"query_parameters":["LAWD_CD","DEAL_YMD"],"lawd_code_length":5,"deal_ymd_format":"YYYYMM","documentation_url":"https://www.data.go.kr/data/15126469/openapi.do"}'::jsonb
  ),
  (
    '20000000-0000-4000-8000-000000000002',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'molit_public'),
    'MOLIT_APT_RENT',
    '국토교통부 아파트 전월세 실거래',
    'APARTMENT',
    'MIXED',
    NULL,
    '2026-07',
    'XML',
    'Asia/Seoul',
    1440,
    true,
    true,
    '{"query_parameters":["LAWD_CD","DEAL_YMD"],"lawd_code_length":5,"deal_ymd_format":"YYYYMM","normalized_trade_types":["JEONSE","MONTHLY_RENT"]}'::jsonb
  )
ON CONFLICT (dataset_code) DO UPDATE SET
  source_id = EXCLUDED.source_id,
  display_name = EXCLUDED.display_name,
  property_type = EXCLUDED.property_type,
  trade_type = EXCLUDED.trade_type,
  endpoint_template = EXCLUDED.endpoint_template,
  api_version = EXCLUDED.api_version,
  response_format = EXCLUDED.response_format,
  timezone = EXCLUDED.timezone,
  freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
  supports_cancellations = EXCLUDED.supports_cancellations,
  enabled = EXCLUDED.enabled,
  metadata = EXCLUDED.metadata;

-- ---------------------------------------------------------------------------
-- Root region. Import the full legal-dong registry through a separate job.
-- ---------------------------------------------------------------------------

INSERT INTO ref.region (
  region_id, code_type, region_code, region_level, name_ko,
  normalized_name, full_path, is_active, metadata
)
VALUES (
  '30000000-0000-4000-8000-000000000001',
  'CUSTOM',
  'KR',
  'COUNTRY',
  '대한민국',
  '대한민국',
  '대한민국',
  true,
  '{"bootstrap_only":true,"note":"Load the official Korean region hierarchy before production ingestion."}'::jsonb
)
ON CONFLICT (code_type, region_code) DO UPDATE SET
  name_ko = EXCLUDED.name_ko,
  normalized_name = EXCLUDED.normalized_name,
  full_path = EXCLUDED.full_path,
  is_active = EXCLUDED.is_active,
  metadata = EXCLUDED.metadata;

-- ---------------------------------------------------------------------------
-- Verified link rules
-- ---------------------------------------------------------------------------

INSERT INTO ref.source_link_rule (
  link_rule_id, source_id, entity_type, view_code, title_template,
  url_template, allowed_host, required_parameters, content_ingested,
  priority, is_active, last_verified_at, metadata
)
VALUES
  (
    '40000000-0000-4000-8000-000000000001',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'molit_rt'),
    'HOME', 'DEFAULT',
    '국토교통부 실거래가 공개시스템',
    'https://rt.molit.go.kr/',
    'rt.molit.go.kr',
    ARRAY[]::text[],
    false, 100, true, TIMESTAMPTZ '2026-08-18 00:00:00+09',
    '{"fallback":true}'::jsonb
  ),
  (
    '40000000-0000-4000-8000-000000000002',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'data_go_kr'),
    'DATASET', 'OPENAPI_DOC',
    '공공데이터포털 API 명세',
    'https://www.data.go.kr/data/{dataset_page_id}/openapi.do',
    'www.data.go.kr',
    ARRAY['dataset_page_id'],
    false, 100, true, TIMESTAMPTZ '2026-08-18 00:00:00+09',
    '{"parameter_patterns":{"dataset_page_id":"^[0-9]{8}$"}}'::jsonb
  ),
  (
    '40000000-0000-4000-8000-000000000003',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'data_go_kr'),
    'HOME', 'DEFAULT',
    '공공데이터포털',
    'https://www.data.go.kr/',
    'www.data.go.kr',
    ARRAY[]::text[],
    false, 200, true, TIMESTAMPTZ '2026-08-18 00:00:00+09',
    '{"fallback":true}'::jsonb
  ),
  (
    '40000000-0000-4000-8000-000000000004',
    (SELECT source_id FROM ref.data_source WHERE source_code = 'apt2me'),
    'HOME', 'DEFAULT',
    '아파트Me에서 원문 확인',
    'https://apt2.me/',
    'apt2.me',
    ARRAY[]::text[],
    false, 100, true, TIMESTAMPTZ '2026-08-18 00:00:00+09',
    '{"fallback":true,"access_mode":"LINK_OUT_ONLY"}'::jsonb
  )
ON CONFLICT (source_id, entity_type, view_code, priority) DO UPDATE SET
  title_template = EXCLUDED.title_template,
  url_template = EXCLUDED.url_template,
  allowed_host = EXCLUDED.allowed_host,
  required_parameters = EXCLUDED.required_parameters,
  content_ingested = EXCLUDED.content_ingested,
  is_active = EXCLUDED.is_active,
  last_verified_at = EXCLUDED.last_verified_at,
  metadata = EXCLUDED.metadata;

-- ---------------------------------------------------------------------------
-- Versioned metric definitions
-- ---------------------------------------------------------------------------

INSERT INTO analytics.metric_definition (
  metric_definition_id, metric_code, formula_version, display_name,
  description, unit, value_type, direction, minimum_sample_count,
  formula_expression, formula_set_version, is_current, effective_from, metadata
)
VALUES
  (
    '50000000-0000-4000-8000-000000000001',
    'LATEST_SALE_PRICE', 'latest_sale_v1', '최신 유효 매매가',
    '동일 면적 범위에서 계약일과 원천 수정 시각 기준 최신 유효 매매 거래 가격',
    'KRW', 'NUMERIC', 'DESC', 1,
    'latest VALID SALE ordered by contract_date, source_last_modified_at, transaction_id',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000002',
    'SALE_MEDIAN_30D', 'sale_median_v1', '최근 30일 매매 중위가',
    '동일 면적 범위 최근 30일 유효 매매가의 중위값',
    'KRW', 'NUMERIC', 'DESC', 1,
    'median(VALID SALE price_krw in inclusive 30-day window)',
    'krams-market-v1', true, DATE '2026-08-18', '{"ranking_minimum_sample_count":3}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000003',
    'SALE_MEDIAN_90D', 'sale_median_v1', '최근 90일 매매 중위가',
    '동일 면적 범위 최근 90일 유효 매매가의 중위값',
    'KRW', 'NUMERIC', 'DESC', 1,
    'median(VALID SALE price_krw in inclusive 90-day window)',
    'krams-market-v1', true, DATE '2026-08-18', '{"ranking_minimum_sample_count":3}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000004',
    'HISTORICAL_PEAK_SALE', 'historical_peak_v1', '역대 신고 최고가',
    '기준일까지 동일 면적 범위의 유효 매매 신고 가격 최댓값',
    'KRW', 'NUMERIC', 'DESC', 1,
    'max(VALID SALE price_krw through as_of_date)',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000005',
    'RECOVERY_RATE_90D', 'recovery_rate_v1', '최고가 회복률',
    '최근 90일 매매 중위가를 역대 신고 최고가로 나눈 백분율',
    'PERCENT', 'NUMERIC', 'DESC', 1,
    'SALE_MEDIAN_90D / HISTORICAL_PEAK_SALE * 100',
    'krams-market-v1', true, DATE '2026-08-18', '{"ranking_minimum_sample_count":3}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000006',
    'LATEST_RECOVERY_RATE', 'latest_recovery_v1', '최신 거래 기준 회복률',
    '최신 유효 매매가를 역대 신고 최고가로 나눈 백분율',
    'PERCENT', 'NUMERIC', 'DESC', 1,
    'LATEST_SALE_PRICE / HISTORICAL_PEAK_SALE * 100',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000007',
    'SALE_VOLUME_30D', 'transaction_volume_v1', '최근 30일 매매 거래량',
    '최근 30일 유효 매매 신고 건수',
    'COUNT', 'NUMERIC', 'DESC', 0,
    'count(VALID SALE in inclusive 30-day window)',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000008',
    'SALE_VOLUME_90D', 'transaction_volume_v1', '최근 90일 매매 거래량',
    '최근 90일 유효 매매 신고 건수',
    'COUNT', 'NUMERIC', 'DESC', 0,
    'count(VALID SALE in inclusive 90-day window)',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000009',
    'VOLUME_MOMENTUM_30D', 'volume_momentum_v1', '30일 거래량 모멘텀',
    '최근 30일 매매 건수를 직전 30일과 비교하며 분모 0은 상태로 분리',
    'RATIO', 'NUMERIC', 'DESC', 0,
    'current_30d_count / previous_30d_count; RESUMED/STOPPED/NO_ACTIVITY states when denominator or numerator is zero',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000010',
    'JEONSE_MEDIAN_90D', 'jeonse_median_v1', '최근 90일 전세 보증금 중위값',
    '동일 면적 범위 최근 90일 유효 전세 보증금의 중위값',
    'KRW', 'NUMERIC', 'DESC', 1,
    'median(VALID JEONSE deposit_krw in inclusive 90-day window)',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000011',
    'JEONSE_RATIO_90D', 'jeonse_ratio_v1', '최근 90일 전세가율',
    '동일 면적·기간의 전세 보증금 중위값을 매매가 중위값으로 나눈 백분율',
    'PERCENT', 'NUMERIC', 'NONE', 1,
    'JEONSE_MEDIAN_90D / SALE_MEDIAN_90D * 100',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000012',
    'ESTIMATED_GAP_90D', 'estimated_gap_v1', '최근 90일 추정 매매·전세 갭',
    '동일 면적·기간의 매매 중위가와 전세 보증금 중위값 차이',
    'KRW', 'NUMERIC', 'ASC', 1,
    'SALE_MEDIAN_90D - JEONSE_MEDIAN_90D',
    'krams-market-v1', true, DATE '2026-08-18', '{"interpretation":"not a matched unit pair"}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000013',
    'NEW_HIGH', 'new_high_v1', '신고가 이벤트',
    '거래일 이전 동일 면적 범위 유효 최고가를 초과한 거래 여부',
    'BOOLEAN', 'BOOLEAN', 'NONE', 1,
    'transaction_price > max(prior VALID SALE price before contract_date)',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000014',
    'SALE_MEDIAN_CHANGE', 'median_change_v1', '기간 매매 중위가 변화율',
    '현재 창과 직전 동일 길이 창의 매매 중위가 변화율',
    'PERCENT', 'NUMERIC', 'DESC', 1,
    '(current_median - previous_median) / previous_median * 100',
    'krams-market-v1', true, DATE '2026-08-18', '{"recommended_sample_count_per_window":3}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000015',
    'SHORT_TERM_TREND_CANDIDATE', 'trend_candidate_v1', '단기 추세 후보',
    '가격·거래량·표본 조건을 모두 충족하는 조건 이벤트이며 미래 가격 예측이 아님',
    'BOOLEAN', 'BOOLEAN', 'NONE', 3,
    'median30 >= median_previous90 * 1.03 AND volume30 >= previous_volume30 AND sample90 >= 3',
    'krams-market-v1', true, DATE '2026-08-18', '{"not_a_forecast":true}'::jsonb
  ),
  (
    '50000000-0000-4000-8000-000000000016',
    'DATA_CONFIDENCE', 'confidence_v1', '데이터 신뢰도',
    '표본·원천 신선도·매핑·품질 플래그를 반영한 해석 보조 등급',
    'STATUS', 'TEXT', 'NONE', 0,
    'HIGH>=5, MEDIUM=3..4, LOW=1..2, INSUFFICIENT=0 with downward quality adjustments',
    'krams-market-v1', true, DATE '2026-08-18', '{}'::jsonb
  )
ON CONFLICT (metric_code, formula_version) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  description = EXCLUDED.description,
  unit = EXCLUDED.unit,
  value_type = EXCLUDED.value_type,
  direction = EXCLUDED.direction,
  minimum_sample_count = EXCLUDED.minimum_sample_count,
  formula_expression = EXCLUDED.formula_expression,
  formula_set_version = EXCLUDED.formula_set_version,
  is_current = EXCLUDED.is_current,
  effective_from = EXCLUDED.effective_from,
  metadata = EXCLUDED.metadata;

COMMIT;
