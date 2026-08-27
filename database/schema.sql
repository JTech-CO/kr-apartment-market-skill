-- KR Apartment Market AI Skill
-- PostgreSQL 16+
-- Schema version: 3.0.0
-- Updated: 2026-08-26
--
-- This migration intentionally does not create login roles or store secrets.
-- Apply with a migration owner, then grant least-privilege roles separately.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA ref IS 'Source, dataset, region, and verified link registries.';
COMMENT ON SCHEMA ingest IS 'Ingestion runs, immutable raw records, partition freshness, and quality issues.';
COMMENT ON SCHEMA market IS 'Apartment complexes, area types, normalized transactions, revisions, and external mappings.';
COMMENT ON SCHEMA analytics IS 'Versioned metrics, snapshots, signals, rankings, and entity change events.';
COMMENT ON SCHEMA app IS 'OAuth-mapped users, watchlists, idempotency records, and delivery cursors.';
COMMENT ON SCHEMA audit IS 'Minimal MCP and user-action audit records without full prompts or tool payloads.';

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := clock_timestamp();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Reference registry
-- ---------------------------------------------------------------------------

CREATE TABLE ref.data_source (
  source_id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code                  text NOT NULL UNIQUE,
  display_name                 text NOT NULL,
  owner_name                   text,
  source_category              text NOT NULL,
  access_mode                  text NOT NULL,
  base_url                     text,
  allowed_hosts                text[] NOT NULL DEFAULT ARRAY[]::text[],
  license_name                 text,
  terms_url                    text,
  privacy_url                  text,
  attribution_template        text,
  authorization_reference     text,
  authorization_verified_at   timestamptz,
  can_ingest                   boolean NOT NULL DEFAULT false,
  can_cache                    boolean NOT NULL DEFAULT false,
  can_redistribute             boolean NOT NULL DEFAULT false,
  can_derive                   boolean NOT NULL DEFAULT false,
  retention_days               integer,
  enabled                      boolean NOT NULL DEFAULT true,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT data_source_code_format_ck
    CHECK (source_code ~ '^[a-z][a-z0-9_]{1,63}$'),
  CONSTRAINT data_source_category_ck
    CHECK (source_category IN ('PUBLIC_API', 'PUBLIC_SITE', 'PARTNER_API', 'LINK_OUT', 'INTERNAL')),
  CONSTRAINT data_source_access_mode_ck
    CHECK (access_mode IN ('PUBLIC_OPEN', 'AUTHORIZED_INGEST', 'LINK_OUT_ONLY', 'DISABLED')),
  CONSTRAINT data_source_https_base_ck
    CHECK (base_url IS NULL OR base_url ~ '^https://'),
  CONSTRAINT data_source_https_terms_ck
    CHECK (terms_url IS NULL OR terms_url ~ '^https://'),
  CONSTRAINT data_source_https_privacy_ck
    CHECK (privacy_url IS NULL OR privacy_url ~ '^https://'),
  CONSTRAINT data_source_retention_ck
    CHECK (retention_days IS NULL OR retention_days >= 0),
  CONSTRAINT data_source_link_out_permissions_ck
    CHECK (
      access_mode <> 'LINK_OUT_ONLY'
      OR NOT (can_ingest OR can_cache OR can_redistribute OR can_derive)
    ),
  CONSTRAINT data_source_disabled_ck
    CHECK (access_mode <> 'DISABLED' OR enabled = false),
  CONSTRAINT data_source_authorized_reference_ck
    CHECK (
      access_mode <> 'AUTHORIZED_INGEST'
      OR (authorization_reference IS NOT NULL AND authorization_verified_at IS NOT NULL)
    )
);

COMMENT ON TABLE ref.data_source IS 'Authoritative access-control registry for every external or internal source.';
COMMENT ON COLUMN ref.data_source.access_mode IS 'PUBLIC_OPEN, AUTHORIZED_INGEST, LINK_OUT_ONLY, or DISABLED.';
COMMENT ON COLUMN ref.data_source.allowed_hosts IS 'HTTPS host allowlist used by source-link generation and adapters.';

CREATE TABLE ref.dataset (
  dataset_id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id                    uuid NOT NULL REFERENCES ref.data_source(source_id) ON DELETE RESTRICT,
  dataset_code                 text NOT NULL UNIQUE,
  display_name                 text NOT NULL,
  property_type                text NOT NULL,
  trade_type                   text,
  endpoint_template            text,
  api_version                  text,
  response_format              text,
  timezone                     text NOT NULL DEFAULT 'Asia/Seoul',
  update_schedule_cron         text,
  freshness_sla_minutes        integer,
  supports_cancellations       boolean NOT NULL DEFAULT false,
  enabled                      boolean NOT NULL DEFAULT true,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT dataset_code_format_ck
    CHECK (dataset_code ~ '^[A-Z][A-Z0-9_]{2,63}$'),
  CONSTRAINT dataset_property_type_ck
    CHECK (property_type IN ('APARTMENT', 'OFFICETEL', 'VILLA', 'PRESALE', 'METADATA', 'MIXED')),
  CONSTRAINT dataset_trade_type_ck
    CHECK (trade_type IS NULL OR trade_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT', 'MIXED')),
  CONSTRAINT dataset_response_format_ck
    CHECK (response_format IS NULL OR response_format IN ('XML', 'JSON', 'CSV', 'HTML', 'INTERNAL')),
  CONSTRAINT dataset_freshness_sla_ck
    CHECK (freshness_sla_minutes IS NULL OR freshness_sla_minutes > 0)
);

COMMENT ON TABLE ref.dataset IS 'Logical datasets exposed by a source, such as apartment sale or apartment rent.';

CREATE TABLE ref.region (
  region_id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code_type                    text NOT NULL,
  region_code                  text NOT NULL,
  region_level                 text NOT NULL,
  name_ko                      text NOT NULL,
  normalized_name              text NOT NULL,
  full_path                    text NOT NULL,
  parent_region_id             uuid REFERENCES ref.region(region_id) ON DELETE RESTRICT,
  lawd_code5                   char(5),
  legal_dong_code10            char(10),
  centroid_latitude            numeric(9,6),
  centroid_longitude           numeric(9,6),
  valid_from                   date NOT NULL DEFAULT DATE '1900-01-01',
  valid_to                     date,
  is_active                    boolean NOT NULL DEFAULT true,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT region_code_unique UNIQUE (code_type, region_code),
  CONSTRAINT region_code_type_ck
    CHECK (code_type IN ('SIDO', 'SIGUNGU', 'LAWD5', 'LEGAL_DONG10', 'ADMIN_DONG', 'CUSTOM')),
  CONSTRAINT region_level_ck
    CHECK (region_level IN ('COUNTRY', 'SIDO', 'SIGUNGU', 'EUPMYEONDONG', 'RI', 'CUSTOM')),
  CONSTRAINT region_lawd_code5_ck
    CHECK (lawd_code5 IS NULL OR lawd_code5 ~ '^[0-9]{5}$'),
  CONSTRAINT region_legal_dong_code10_ck
    CHECK (legal_dong_code10 IS NULL OR legal_dong_code10 ~ '^[0-9]{10}$'),
  CONSTRAINT region_latitude_ck
    CHECK (centroid_latitude IS NULL OR centroid_latitude BETWEEN -90 AND 90),
  CONSTRAINT region_longitude_ck
    CHECK (centroid_longitude IS NULL OR centroid_longitude BETWEEN -180 AND 180),
  CONSTRAINT region_valid_range_ck
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

COMMENT ON TABLE ref.region IS 'Hierarchical Korean region registry with legal-dong API codes.';

CREATE TABLE ref.region_alias (
  region_alias_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id                    uuid NOT NULL REFERENCES ref.region(region_id) ON DELETE CASCADE,
  alias                        text NOT NULL,
  normalized_alias             text NOT NULL,
  alias_type                   text NOT NULL DEFAULT 'SEARCH',
  source_id                    uuid REFERENCES ref.data_source(source_id) ON DELETE SET NULL,
  locale                       text NOT NULL DEFAULT 'ko-KR',
  is_preferred                 boolean NOT NULL DEFAULT false,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT region_alias_unique UNIQUE (region_id, normalized_alias, locale),
  CONSTRAINT region_alias_type_ck
    CHECK (alias_type IN ('SEARCH', 'HISTORICAL', 'ABBREVIATION', 'ROMANIZED', 'SOURCE'))
);

CREATE TABLE ref.source_link_rule (
  link_rule_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id                    uuid NOT NULL REFERENCES ref.data_source(source_id) ON DELETE CASCADE,
  entity_type                  text NOT NULL,
  view_code                    text NOT NULL DEFAULT 'DEFAULT',
  title_template               text NOT NULL,
  url_template                 text NOT NULL,
  allowed_host                 text NOT NULL,
  required_parameters          text[] NOT NULL DEFAULT ARRAY[]::text[],
  content_ingested             boolean NOT NULL DEFAULT false,
  priority                     integer NOT NULL DEFAULT 100,
  is_active                    boolean NOT NULL DEFAULT true,
  last_verified_at             timestamptz,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT source_link_rule_unique UNIQUE (source_id, entity_type, view_code, priority),
  CONSTRAINT source_link_entity_type_ck
    CHECK (entity_type IN ('HOME', 'COMPLEX', 'REGION', 'DATASET', 'RANKING')),
  CONSTRAINT source_link_https_ck
    CHECK (url_template ~ '^https://'),
  CONSTRAINT source_link_host_format_ck
    CHECK (allowed_host ~ '^[A-Za-z0-9.-]+$')
);

COMMENT ON TABLE ref.source_link_rule IS 'Verified HTTPS templates used by get_source_link; never accepts arbitrary user hosts.';

-- ---------------------------------------------------------------------------
-- Ingestion
-- ---------------------------------------------------------------------------

CREATE TABLE ingest.ingestion_run (
  ingestion_run_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id                   uuid NOT NULL REFERENCES ref.dataset(dataset_id) ON DELETE RESTRICT,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE SET NULL,
  partition_key                text,
  requested_contract_month     char(6),
  status                       text NOT NULL DEFAULT 'RUNNING',
  trigger_type                 text NOT NULL DEFAULT 'SCHEDULED',
  parser_version               text NOT NULL,
  started_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at                  timestamptz,
  source_watermark_at          timestamptz,
  latest_contract_date         date,
  request_count                integer NOT NULL DEFAULT 0,
  response_record_count        integer NOT NULL DEFAULT 0,
  inserted_count               integer NOT NULL DEFAULT 0,
  updated_count                integer NOT NULL DEFAULT 0,
  canceled_count               integer NOT NULL DEFAULT 0,
  rejected_count               integer NOT NULL DEFAULT 0,
  error_code                   text,
  error_summary                text,
  correlation_id_hash          char(64),
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT ingestion_run_month_ck
    CHECK (requested_contract_month IS NULL OR requested_contract_month ~ '^[0-9]{6}$'),
  CONSTRAINT ingestion_run_status_ck
    CHECK (status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED', 'CANCELED')),
  CONSTRAINT ingestion_run_trigger_ck
    CHECK (trigger_type IN ('SCHEDULED', 'MANUAL', 'BACKFILL', 'RECONCILIATION', 'RETRY')),
  CONSTRAINT ingestion_run_finished_ck
    CHECK (finished_at IS NULL OR finished_at >= started_at),
  CONSTRAINT ingestion_run_counts_ck
    CHECK (
      request_count >= 0 AND response_record_count >= 0 AND inserted_count >= 0
      AND updated_count >= 0 AND canceled_count >= 0 AND rejected_count >= 0
    )
);

CREATE TABLE ingest.raw_record (
  raw_record_id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ingestion_run_id             uuid NOT NULL REFERENCES ingest.ingestion_run(ingestion_run_id) ON DELETE CASCADE,
  dataset_id                   uuid NOT NULL REFERENCES ref.dataset(dataset_id) ON DELETE RESTRICT,
  source_record_key            text,
  source_record_hash           char(64) NOT NULL,
  payload                      jsonb NOT NULL,
  payload_size_bytes           integer,
  collected_at                 timestamptz NOT NULL DEFAULT clock_timestamp(),
  parsed_at                    timestamptz,
  parse_status                 text NOT NULL DEFAULT 'PENDING',
  parser_version               text,
  parse_error_code             text,
  parse_error_summary          text,
  CONSTRAINT raw_record_hash_ck
    CHECK (source_record_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT raw_record_size_ck
    CHECK (payload_size_bytes IS NULL OR payload_size_bytes >= 0),
  CONSTRAINT raw_record_parse_status_ck
    CHECK (parse_status IN ('PENDING', 'PARSED', 'REJECTED', 'QUARANTINED'))
);

COMMENT ON TABLE ingest.raw_record IS 'Immutable record-level source payload after removing credentials and transport secrets.';

CREATE TABLE ingest.dataset_partition_state (
  dataset_partition_state_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id                   uuid NOT NULL REFERENCES ref.dataset(dataset_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  partition_key                text NOT NULL DEFAULT 'GLOBAL',
  freshness_status             text NOT NULL DEFAULT 'UNKNOWN',
  last_attempt_at              timestamptz,
  last_successful_collection_at timestamptz,
  source_watermark_at          timestamptz,
  latest_contract_date         date,
  next_scheduled_collection_at timestamptz,
  delay_minutes                integer,
  coverage_note                text,
  last_ingestion_run_id        uuid REFERENCES ingest.ingestion_run(ingestion_run_id) ON DELETE SET NULL,
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT dataset_partition_state_unique UNIQUE NULLS NOT DISTINCT (dataset_id, region_id, partition_key),
  CONSTRAINT dataset_partition_freshness_ck
    CHECK (freshness_status IN ('CURRENT', 'PARTIAL', 'DELAYED', 'UNAVAILABLE', 'UNKNOWN')),
  CONSTRAINT dataset_partition_delay_ck
    CHECK (delay_minutes IS NULL OR delay_minutes >= 0)
);

-- ---------------------------------------------------------------------------
-- Market master and transactions
-- ---------------------------------------------------------------------------

CREATE TABLE market.complex (
  complex_id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complex_key                  text NOT NULL UNIQUE,
  primary_region_id            uuid NOT NULL REFERENCES ref.region(region_id) ON DELETE RESTRICT,
  complex_name                 text NOT NULL,
  normalized_name              text NOT NULL,
  road_address                 text,
  jibun_address                text,
  household_count              integer,
  building_count               integer,
  approval_date                date,
  built_year                   smallint,
  maximum_floor                smallint,
  latitude                     numeric(9,6),
  longitude                    numeric(9,6),
  status                       text NOT NULL DEFAULT 'ACTIVE',
  mapping_confidence           numeric(5,4) NOT NULL DEFAULT 1.0000,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT complex_key_format_ck
    CHECK (complex_key ~ '^[a-z0-9][a-z0-9:_-]{2,127}$'),
  CONSTRAINT complex_household_count_ck
    CHECK (household_count IS NULL OR household_count >= 0),
  CONSTRAINT complex_building_count_ck
    CHECK (building_count IS NULL OR building_count >= 0),
  CONSTRAINT complex_built_year_ck
    CHECK (built_year IS NULL OR built_year BETWEEN 1900 AND 2200),
  CONSTRAINT complex_maximum_floor_ck
    CHECK (maximum_floor IS NULL OR maximum_floor BETWEEN -20 AND 300),
  CONSTRAINT complex_latitude_ck
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT complex_longitude_ck
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  CONSTRAINT complex_status_ck
    CHECK (status IN ('ACTIVE', 'RENAMED', 'REDEVELOPED', 'DEMOLISHED', 'UNVERIFIED', 'INACTIVE')),
  CONSTRAINT complex_mapping_confidence_ck
    CHECK (mapping_confidence BETWEEN 0 AND 1)
);

CREATE TABLE market.complex_alias (
  complex_alias_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complex_id                   uuid NOT NULL REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  alias                        text NOT NULL,
  normalized_alias             text NOT NULL,
  alias_type                   text NOT NULL DEFAULT 'SEARCH',
  source_id                    uuid REFERENCES ref.data_source(source_id) ON DELETE SET NULL,
  locale                       text NOT NULL DEFAULT 'ko-KR',
  valid_from                   date,
  valid_to                     date,
  is_preferred                 boolean NOT NULL DEFAULT false,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT complex_alias_unique UNIQUE (complex_id, normalized_alias, locale),
  CONSTRAINT complex_alias_type_ck
    CHECK (alias_type IN ('SEARCH', 'HISTORICAL', 'ROMANIZED', 'SOURCE', 'MARKETING')),
  CONSTRAINT complex_alias_valid_range_ck
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE TABLE market.area_type (
  area_type_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complex_id                   uuid NOT NULL REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  exclusive_area_m2            numeric(8,2) NOT NULL,
  supply_area_m2               numeric(8,2),
  type_label                   text,
  room_count                   smallint,
  bathroom_count               smallint,
  household_count              integer,
  is_active                    boolean NOT NULL DEFAULT true,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT area_type_exclusive_ck
    CHECK (exclusive_area_m2 > 0 AND exclusive_area_m2 <= 1000),
  CONSTRAINT area_type_supply_ck
    CHECK (supply_area_m2 IS NULL OR (supply_area_m2 > 0 AND supply_area_m2 <= 1500)),
  CONSTRAINT area_type_rooms_ck
    CHECK (room_count IS NULL OR room_count BETWEEN 0 AND 30),
  CONSTRAINT area_type_bathrooms_ck
    CHECK (bathroom_count IS NULL OR bathroom_count BETWEEN 0 AND 30),
  CONSTRAINT area_type_households_ck
    CHECK (household_count IS NULL OR household_count >= 0),
  CONSTRAINT area_type_complex_identity_uq
    UNIQUE (complex_id, area_type_id)
);

CREATE UNIQUE INDEX area_type_identity_uq
  ON market.area_type (complex_id, exclusive_area_m2, COALESCE(type_label, ''));

CREATE TABLE market.external_entity_map (
  external_entity_map_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id                    uuid NOT NULL REFERENCES ref.data_source(source_id) ON DELETE CASCADE,
  entity_type                  text NOT NULL,
  external_id                  text NOT NULL,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  external_url_path            text,
  mapping_confidence           numeric(5,4) NOT NULL DEFAULT 1.0000,
  verified_manually            boolean NOT NULL DEFAULT false,
  verified_at                  timestamptz,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT external_entity_map_unique UNIQUE (source_id, entity_type, external_id),
  CONSTRAINT external_entity_type_ck
    CHECK (entity_type IN ('COMPLEX', 'REGION')),
  CONSTRAINT external_entity_target_ck
    CHECK (
      (entity_type = 'COMPLEX' AND complex_id IS NOT NULL AND region_id IS NULL)
      OR (entity_type = 'REGION' AND region_id IS NOT NULL AND complex_id IS NULL)
    ),
  CONSTRAINT external_entity_confidence_ck
    CHECK (mapping_confidence BETWEEN 0 AND 1),
  CONSTRAINT external_url_path_ck
    CHECK (external_url_path IS NULL OR external_url_path ~ '^/')
);

CREATE TABLE market.real_estate_transaction (
  transaction_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id                   uuid NOT NULL REFERENCES ref.dataset(dataset_id) ON DELETE RESTRICT,
  raw_record_id                bigint REFERENCES ingest.raw_record(raw_record_id) ON DELETE SET NULL,
  source_record_key            text NOT NULL,
  natural_key_hash             char(64) NOT NULL,
  source_payload_hash          char(64) NOT NULL,
  property_type                text NOT NULL DEFAULT 'APARTMENT',
  trade_type                   text NOT NULL,
  region_id                    uuid NOT NULL REFERENCES ref.region(region_id) ON DELETE RESTRICT,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE SET NULL,
  area_type_id                 uuid,
  original_complex_name        text NOT NULL,
  contract_date                date NOT NULL,
  reported_at                  timestamptz,
  registration_date            date,
  price_krw                    bigint,
  deposit_krw                  bigint,
  monthly_rent_krw             bigint,
  exclusive_area_m2            numeric(8,2) NOT NULL,
  floor                        smallint,
  built_year                   smallint,
  transaction_method           text NOT NULL DEFAULT 'UNKNOWN',
  broker_region_text           text,
  record_status                text NOT NULL DEFAULT 'VALID',
  canceled_at                  date,
  source_last_modified_at      timestamptz,
  first_collected_at           timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_collected_at            timestamptz NOT NULL DEFAULT clock_timestamp(),
  current_revision_no          integer NOT NULL DEFAULT 1,
  quality_flags                text[] NOT NULL DEFAULT ARRAY[]::text[],
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT transaction_source_key_unique UNIQUE (dataset_id, source_record_key),
  CONSTRAINT transaction_natural_hash_ck
    CHECK (natural_key_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT transaction_payload_hash_ck
    CHECK (source_payload_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT transaction_property_type_ck
    CHECK (property_type IN ('APARTMENT', 'OFFICETEL', 'VILLA', 'PRESALE')),
  CONSTRAINT transaction_trade_type_ck
    CHECK (trade_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT')),
  CONSTRAINT transaction_money_nonnegative_ck
    CHECK (
      (price_krw IS NULL OR price_krw >= 0)
      AND (deposit_krw IS NULL OR deposit_krw >= 0)
      AND (monthly_rent_krw IS NULL OR monthly_rent_krw >= 0)
    ),
  CONSTRAINT transaction_trade_amount_ck
    CHECK (
      (trade_type = 'SALE' AND price_krw IS NOT NULL AND price_krw > 0
       AND deposit_krw IS NULL AND monthly_rent_krw IS NULL)
      OR
      (trade_type = 'JEONSE' AND deposit_krw IS NOT NULL AND deposit_krw > 0
       AND price_krw IS NULL AND COALESCE(monthly_rent_krw, 0) = 0)
      OR
      (trade_type = 'MONTHLY_RENT' AND deposit_krw IS NOT NULL AND deposit_krw >= 0
       AND monthly_rent_krw IS NOT NULL AND monthly_rent_krw > 0
       AND price_krw IS NULL)
    ),
  CONSTRAINT transaction_area_type_scope_ck
    CHECK (area_type_id IS NULL OR complex_id IS NOT NULL),
  CONSTRAINT transaction_area_type_complex_fk
    FOREIGN KEY (complex_id, area_type_id)
    REFERENCES market.area_type (complex_id, area_type_id)
    ON DELETE SET NULL (area_type_id),
  CONSTRAINT transaction_area_ck
    CHECK (exclusive_area_m2 > 0 AND exclusive_area_m2 <= 1000),
  CONSTRAINT transaction_floor_ck
    CHECK (floor IS NULL OR floor BETWEEN -20 AND 300),
  CONSTRAINT transaction_built_year_ck
    CHECK (built_year IS NULL OR built_year BETWEEN 1900 AND 2200),
  CONSTRAINT transaction_method_ck
    CHECK (transaction_method IN ('BROKERED', 'DIRECT', 'UNKNOWN')),
  CONSTRAINT transaction_record_status_ck
    CHECK (record_status IN ('VALID', 'CANCELED')),
  CONSTRAINT transaction_revision_no_ck
    CHECK (current_revision_no >= 1),
  CONSTRAINT transaction_collection_order_ck
    CHECK (last_collected_at >= first_collected_at)
);

COMMENT ON TABLE market.real_estate_transaction IS 'Current normalized state of each source transaction; canceled rows remain for history.';

CREATE TABLE market.transaction_revision (
  transaction_revision_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  transaction_id              uuid NOT NULL REFERENCES market.real_estate_transaction(transaction_id) ON DELETE CASCADE,
  revision_no                 integer NOT NULL,
  operation                   text NOT NULL,
  raw_record_id               bigint REFERENCES ingest.raw_record(raw_record_id) ON DELETE SET NULL,
  source_payload_hash         char(64) NOT NULL,
  changed_fields              text[] NOT NULL DEFAULT ARRAY[]::text[],
  snapshot                    jsonb NOT NULL,
  valid_from                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  valid_to                    timestamptz,
  created_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT transaction_revision_unique UNIQUE (transaction_id, revision_no),
  CONSTRAINT transaction_revision_no_ck CHECK (revision_no >= 1),
  CONSTRAINT transaction_revision_operation_ck
    CHECK (operation IN ('INSERT', 'UPDATE', 'CANCEL', 'REACTIVATE')),
  CONSTRAINT transaction_revision_hash_ck
    CHECK (source_payload_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT transaction_revision_valid_range_ck
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE ingest.data_quality_issue (
  data_quality_issue_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingestion_run_id             uuid REFERENCES ingest.ingestion_run(ingestion_run_id) ON DELETE SET NULL,
  raw_record_id                bigint REFERENCES ingest.raw_record(raw_record_id) ON DELETE SET NULL,
  transaction_id               uuid REFERENCES market.real_estate_transaction(transaction_id) ON DELETE SET NULL,
  issue_code                   text NOT NULL,
  severity                     text NOT NULL,
  status                       text NOT NULL DEFAULT 'OPEN',
  field_name                   text,
  summary                      text NOT NULL,
  details                      jsonb NOT NULL DEFAULT '{}'::jsonb,
  detected_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  resolved_at                  timestamptz,
  resolution_note              text,
  CONSTRAINT data_quality_severity_ck
    CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'BLOCKING')),
  CONSTRAINT data_quality_status_ck
    CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED')),
  CONSTRAINT data_quality_resolution_ck
    CHECK (resolved_at IS NULL OR resolved_at >= detected_at)
);

-- ---------------------------------------------------------------------------
-- Analytics
-- ---------------------------------------------------------------------------

CREATE TABLE analytics.metric_definition (
  metric_definition_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_code                 text NOT NULL,
  formula_version             text NOT NULL,
  display_name                text NOT NULL,
  description                 text NOT NULL,
  unit                         text NOT NULL,
  value_type                   text NOT NULL DEFAULT 'NUMERIC',
  direction                    text NOT NULL DEFAULT 'NONE',
  minimum_sample_count        integer NOT NULL DEFAULT 1,
  formula_expression          text NOT NULL,
  formula_set_version         text NOT NULL DEFAULT 'krams-market-v1',
  is_current                  boolean NOT NULL DEFAULT true,
  effective_from              date NOT NULL DEFAULT CURRENT_DATE,
  effective_to                date,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT metric_definition_unique UNIQUE (metric_code, formula_version),
  CONSTRAINT metric_code_format_ck
    CHECK (metric_code ~ '^[A-Z][A-Z0-9_]{2,63}$'),
  CONSTRAINT metric_unit_ck
    CHECK (unit IN ('KRW', 'COUNT', 'PERCENT', 'RATIO', 'BOOLEAN', 'STATUS', 'DATE', 'NONE')),
  CONSTRAINT metric_value_type_ck
    CHECK (value_type IN ('NUMERIC', 'TEXT', 'BOOLEAN', 'DATE')),
  CONSTRAINT metric_direction_ck
    CHECK (direction IN ('ASC', 'DESC', 'NONE')),
  CONSTRAINT metric_sample_ck
    CHECK (minimum_sample_count >= 0),
  CONSTRAINT metric_effective_range_ck
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE UNIQUE INDEX metric_definition_one_current_uq
  ON analytics.metric_definition (metric_code)
  WHERE is_current;

CREATE TABLE analytics.analysis_snapshot (
  snapshot_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_key                 text NOT NULL UNIQUE,
  scope_type                   text NOT NULL,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  area_type_id                 uuid,
  area_min_m2                  numeric(8,2),
  area_max_m2                  numeric(8,2),
  window_start                 date NOT NULL,
  window_end                   date NOT NULL,
  comparison_window_start      date,
  comparison_window_end        date,
  as_of_date                   date NOT NULL,
  formula_set_version          text NOT NULL,
  freshness_status             text NOT NULL,
  source_watermark_at          timestamptz,
  computed_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  is_partial_period            boolean NOT NULL DEFAULT false,
  filter_spec                  jsonb NOT NULL DEFAULT '{}'::jsonb,
  quality_summary              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT analysis_snapshot_scope_ck
    CHECK (
      (scope_type = 'COMPLEX' AND complex_id IS NOT NULL AND region_id IS NULL)
      OR (scope_type = 'REGION' AND region_id IS NOT NULL AND complex_id IS NULL)
    ),
  CONSTRAINT analysis_snapshot_scope_type_ck
    CHECK (scope_type IN ('COMPLEX', 'REGION')),
  CONSTRAINT analysis_snapshot_area_ck
    CHECK (
      (area_min_m2 IS NULL AND area_max_m2 IS NULL)
      OR (area_min_m2 IS NOT NULL AND area_max_m2 IS NOT NULL
          AND area_min_m2 > 0 AND area_max_m2 >= area_min_m2)
    ),
  CONSTRAINT analysis_snapshot_area_type_scope_ck
    CHECK (area_type_id IS NULL OR complex_id IS NOT NULL),
  CONSTRAINT analysis_snapshot_area_selector_ck
    CHECK (area_type_id IS NULL OR (area_min_m2 IS NULL AND area_max_m2 IS NULL)),
  CONSTRAINT analysis_snapshot_area_type_complex_fk
    FOREIGN KEY (complex_id, area_type_id)
    REFERENCES market.area_type (complex_id, area_type_id)
    ON DELETE SET NULL (area_type_id),
  CONSTRAINT analysis_snapshot_window_ck
    CHECK (window_end >= window_start AND as_of_date >= window_end),
  CONSTRAINT analysis_snapshot_comparison_window_ck
    CHECK (
      (comparison_window_start IS NULL AND comparison_window_end IS NULL)
      OR (comparison_window_start IS NOT NULL AND comparison_window_end IS NOT NULL
          AND comparison_window_end >= comparison_window_start)
    ),
  CONSTRAINT analysis_snapshot_freshness_ck
    CHECK (freshness_status IN ('CURRENT', 'PARTIAL', 'DELAYED', 'UNAVAILABLE', 'UNKNOWN'))
);

CREATE TABLE analytics.metric_value (
  metric_value_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id                  uuid NOT NULL REFERENCES analytics.analysis_snapshot(snapshot_id) ON DELETE CASCADE,
  metric_definition_id         uuid NOT NULL REFERENCES analytics.metric_definition(metric_definition_id) ON DELETE RESTRICT,
  status                       text NOT NULL DEFAULT 'OK',
  value_numeric                numeric(30,8),
  value_text                   text,
  value_boolean                boolean,
  value_date                   date,
  numerator_numeric            numeric(30,8),
  denominator_numeric          numeric(30,8),
  sample_count                 integer NOT NULL DEFAULT 0,
  comparison_sample_count      integer,
  evidence                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  computed_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT metric_value_unique UNIQUE (snapshot_id, metric_definition_id),
  CONSTRAINT metric_value_status_ck
    CHECK (status IN ('OK', 'LOW_SAMPLE', 'INSUFFICIENT_DATA', 'PARTIAL_PERIOD', 'SOURCE_DELAYED', 'NOT_COMPARABLE', 'NOT_APPLICABLE')),
  CONSTRAINT metric_value_one_value_ck
    CHECK (
      (status IN ('OK', 'LOW_SAMPLE', 'PARTIAL_PERIOD', 'SOURCE_DELAYED')
       AND num_nonnulls(value_numeric, value_text, value_boolean, value_date) = 1)
      OR
      (status IN ('INSUFFICIENT_DATA', 'NOT_COMPARABLE', 'NOT_APPLICABLE')
       AND num_nonnulls(value_numeric, value_text, value_boolean, value_date) = 0)
    ),
  CONSTRAINT metric_value_samples_ck
    CHECK (sample_count >= 0 AND (comparison_sample_count IS NULL OR comparison_sample_count >= 0))
);

CREATE TABLE analytics.signal_event (
  signal_event_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dedup_key                    text NOT NULL UNIQUE,
  signal_type                  text NOT NULL,
  state                        text NOT NULL,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  area_type_id                 uuid,
  area_min_m2                  numeric(8,2),
  area_max_m2                  numeric(8,2),
  formula_version              text NOT NULL,
  detected_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  started_at                   timestamptz NOT NULL,
  ended_at                     timestamptz,
  source_watermark_at          timestamptz,
  sample_count                 integer NOT NULL DEFAULT 0,
  evidence                     jsonb NOT NULL,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT signal_type_ck
    CHECK (signal_type IN ('NEW_HIGH', 'VOLUME_RESUMED', 'SHORT_TERM_TREND_CANDIDATE', 'VOLUME_STOPPED')),
  CONSTRAINT signal_state_ck
    CHECK (state IN ('STARTED', 'ACTIVE', 'ENDED', 'RETRACTED')),
  CONSTRAINT signal_scope_ck
    CHECK (
      (complex_id IS NOT NULL AND region_id IS NULL)
      OR (region_id IS NOT NULL AND complex_id IS NULL)
    ),
  CONSTRAINT signal_area_ck
    CHECK (
      (area_min_m2 IS NULL AND area_max_m2 IS NULL)
      OR (area_min_m2 IS NOT NULL AND area_max_m2 IS NOT NULL
          AND area_min_m2 > 0 AND area_max_m2 >= area_min_m2)
    ),
  CONSTRAINT signal_area_type_scope_ck
    CHECK (area_type_id IS NULL OR complex_id IS NOT NULL),
  CONSTRAINT signal_area_selector_ck
    CHECK (area_type_id IS NULL OR (area_min_m2 IS NULL AND area_max_m2 IS NULL)),
  CONSTRAINT signal_area_type_complex_fk
    FOREIGN KEY (complex_id, area_type_id)
    REFERENCES market.area_type (complex_id, area_type_id)
    ON DELETE SET NULL (area_type_id),
  CONSTRAINT signal_dates_ck
    CHECK (ended_at IS NULL OR ended_at >= started_at),
  CONSTRAINT signal_samples_ck
    CHECK (sample_count >= 0)
);

CREATE TABLE analytics.ranking_run (
  ranking_run_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ranking_key                  text NOT NULL UNIQUE,
  region_id                    uuid NOT NULL REFERENCES ref.region(region_id) ON DELETE CASCADE,
  metric_definition_id         uuid NOT NULL REFERENCES analytics.metric_definition(metric_definition_id) ON DELETE RESTRICT,
  area_min_m2                  numeric(8,2),
  area_max_m2                  numeric(8,2),
  period_start                 date NOT NULL,
  period_end                   date NOT NULL,
  as_of_date                   date NOT NULL,
  sort_direction               text NOT NULL,
  minimum_sample_count         integer NOT NULL,
  filter_spec                  jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_watermark_at          timestamptz,
  computed_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT ranking_run_area_ck
    CHECK (
      (area_min_m2 IS NULL AND area_max_m2 IS NULL)
      OR (area_min_m2 IS NOT NULL AND area_max_m2 IS NOT NULL
          AND area_min_m2 > 0 AND area_max_m2 >= area_min_m2)
    ),
  CONSTRAINT ranking_run_period_ck
    CHECK (period_end >= period_start AND as_of_date >= period_end),
  CONSTRAINT ranking_run_direction_ck
    CHECK (sort_direction IN ('ASC', 'DESC')),
  CONSTRAINT ranking_run_sample_ck
    CHECK (minimum_sample_count >= 1)
);

CREATE TABLE analytics.ranking_entry (
  ranking_entry_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ranking_run_id               uuid NOT NULL REFERENCES analytics.ranking_run(ranking_run_id) ON DELETE CASCADE,
  rank                         integer NOT NULL,
  tie_group                    integer,
  complex_id                   uuid NOT NULL REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  metric_value_numeric         numeric(30,8),
  metric_value_text            text,
  sample_count                 integer NOT NULL,
  snapshot_id                  uuid REFERENCES analytics.analysis_snapshot(snapshot_id) ON DELETE SET NULL,
  warnings                     jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT ranking_entry_unique UNIQUE (ranking_run_id, complex_id),
  CONSTRAINT ranking_entry_rank_ck CHECK (rank >= 1),
  CONSTRAINT ranking_entry_tie_ck CHECK (tie_group IS NULL OR tie_group >= 1),
  CONSTRAINT ranking_entry_value_ck
    CHECK (num_nonnulls(metric_value_numeric, metric_value_text) = 1),
  CONSTRAINT ranking_entry_sample_ck CHECK (sample_count >= 0)
);

CREATE TABLE analytics.entity_change_event (
  event_id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dedup_key                    text NOT NULL UNIQUE,
  event_type                   text NOT NULL,
  occurred_at                  timestamptz NOT NULL,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  transaction_id               uuid REFERENCES market.real_estate_transaction(transaction_id) ON DELETE CASCADE,
  signal_event_id              uuid REFERENCES analytics.signal_event(signal_event_id) ON DELETE CASCADE,
  payload                      jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_watermark_at          timestamptz,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT entity_change_event_type_ck
    CHECK (event_type IN (
      'NEW_TRANSACTION', 'CORRECTED_TRANSACTION', 'CANCELED_TRANSACTION',
      'NEW_HIGH', 'SIGNAL_STARTED', 'SIGNAL_ENDED', 'SIGNAL_RETRACTED'
    )),
  CONSTRAINT entity_change_event_scope_ck
    CHECK (complex_id IS NOT NULL OR region_id IS NOT NULL),
  CONSTRAINT entity_change_event_reference_ck
    CHECK (transaction_id IS NOT NULL OR signal_event_id IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- Application and OAuth-bound state
-- ---------------------------------------------------------------------------

CREATE TABLE app.app_user (
  user_id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_issuer                  text NOT NULL,
  auth_subject_hash            char(64) NOT NULL,
  status                       text NOT NULL DEFAULT 'ACTIVE',
  locale                       text NOT NULL DEFAULT 'ko-KR',
  timezone                     text NOT NULL DEFAULT 'Asia/Seoul',
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_seen_at                 timestamptz,
  deleted_at                   timestamptz,
  CONSTRAINT app_user_identity_unique UNIQUE (auth_issuer, auth_subject_hash),
  CONSTRAINT app_user_issuer_https_ck CHECK (auth_issuer ~ '^https://'),
  CONSTRAINT app_user_subject_hash_ck CHECK (auth_subject_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT app_user_status_ck CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DELETED'))
);

COMMENT ON COLUMN app.app_user.auth_subject_hash IS 'Peppered one-way hash; raw OAuth subject must not be stored.';

CREATE TABLE app.watchlist (
  watchlist_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  name                         text NOT NULL,
  is_default                   boolean NOT NULL DEFAULT false,
  is_active                    boolean NOT NULL DEFAULT true,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at                   timestamptz,
  CONSTRAINT watchlist_name_length_ck CHECK (char_length(name) BETWEEN 1 AND 100)
);

CREATE UNIQUE INDEX watchlist_one_default_uq
  ON app.watchlist (user_id)
  WHERE is_default AND deleted_at IS NULL;

CREATE UNIQUE INDEX watchlist_active_name_uq
  ON app.watchlist (user_id, lower(name))
  WHERE deleted_at IS NULL;

CREATE TABLE app.watchlist_item (
  watchlist_item_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id                 uuid NOT NULL REFERENCES app.watchlist(watchlist_id) ON DELETE CASCADE,
  entity_type                  text NOT NULL,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE CASCADE,
  region_id                    uuid REFERENCES ref.region(region_id) ON DELETE CASCADE,
  area_type_id                 uuid,
  area_min_m2                  numeric(8,2),
  area_max_m2                  numeric(8,2),
  trade_types                  text[] NOT NULL DEFAULT ARRAY['SALE']::text[],
  signal_rules                 jsonb NOT NULL DEFAULT '[]'::jsonb,
  label                        text,
  natural_key_hash             char(64) NOT NULL,
  is_active                    boolean NOT NULL DEFAULT true,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at                   timestamptz,
  CONSTRAINT watchlist_item_entity_type_ck CHECK (entity_type IN ('COMPLEX', 'REGION')),
  CONSTRAINT watchlist_item_target_ck
    CHECK (
      (entity_type = 'COMPLEX' AND complex_id IS NOT NULL AND region_id IS NULL)
      OR (entity_type = 'REGION' AND region_id IS NOT NULL AND complex_id IS NULL)
    ),
  CONSTRAINT watchlist_item_area_type_scope_ck CHECK (area_type_id IS NULL OR complex_id IS NOT NULL),
  CONSTRAINT watchlist_item_area_selector_ck
    CHECK (area_type_id IS NULL OR (area_min_m2 IS NULL AND area_max_m2 IS NULL)),
  CONSTRAINT watchlist_item_area_type_complex_fk
    FOREIGN KEY (complex_id, area_type_id)
    REFERENCES market.area_type (complex_id, area_type_id)
    ON DELETE SET NULL (area_type_id),
  CONSTRAINT watchlist_item_area_ck
    CHECK (
      (area_min_m2 IS NULL AND area_max_m2 IS NULL)
      OR (area_min_m2 IS NOT NULL AND area_max_m2 IS NOT NULL
          AND area_min_m2 > 0 AND area_max_m2 >= area_min_m2)
    ),
  CONSTRAINT watchlist_item_trade_types_ck
    CHECK (
      cardinality(trade_types) >= 1
      AND trade_types <@ ARRAY['SALE', 'JEONSE', 'MONTHLY_RENT']::text[]
    ),
  CONSTRAINT watchlist_item_signal_rules_array_ck CHECK (jsonb_typeof(signal_rules) = 'array'),
  CONSTRAINT watchlist_item_label_length_ck CHECK (label IS NULL OR char_length(label) <= 100),
  CONSTRAINT watchlist_item_natural_hash_ck CHECK (natural_key_hash ~ '^[0-9a-f]{64}$')
);

CREATE UNIQUE INDEX watchlist_item_active_natural_key_uq
  ON app.watchlist_item (watchlist_id, natural_key_hash)
  WHERE deleted_at IS NULL;

CREATE TABLE app.idempotency_record (
  idempotency_record_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  operation_name               text NOT NULL,
  idempotency_key              text NOT NULL,
  request_hash                 char(64) NOT NULL,
  response_status              integer NOT NULL,
  response_body                jsonb NOT NULL,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  expires_at                   timestamptz NOT NULL,
  CONSTRAINT idempotency_record_unique UNIQUE (user_id, operation_name, idempotency_key),
  CONSTRAINT idempotency_request_hash_ck CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT idempotency_status_ck CHECK (response_status BETWEEN 100 AND 599),
  CONSTRAINT idempotency_expiry_ck CHECK (expires_at > created_at)
);

CREATE TABLE app.watchlist_delivery_cursor (
  watchlist_delivery_cursor_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id                 uuid NOT NULL REFERENCES app.watchlist(watchlist_id) ON DELETE CASCADE,
  channel_code                 text NOT NULL,
  last_delivered_event_at      timestamptz,
  last_delivered_event_id      uuid REFERENCES analytics.entity_change_event(event_id) ON DELETE SET NULL,
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT watchlist_delivery_cursor_unique UNIQUE (watchlist_id, channel_code),
  CONSTRAINT watchlist_delivery_channel_ck CHECK (channel_code ~ '^[A-Z][A-Z0-9_]{1,31}$')
);

-- ---------------------------------------------------------------------------
-- Audit and observability
-- ---------------------------------------------------------------------------

CREATE TABLE audit.mcp_tool_call (
  mcp_tool_call_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  request_id_hash              char(64),
  user_id                      uuid REFERENCES app.app_user(user_id) ON DELETE SET NULL,
  tool_name                    text NOT NULL,
  started_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at                  timestamptz,
  duration_ms                  integer,
  outcome                      text NOT NULL,
  error_code                   text,
  cache_hit                    boolean,
  dataset_codes               text[] NOT NULL DEFAULT ARRAY[]::text[],
  returned_row_bucket          text,
  authenticated               boolean NOT NULL DEFAULT false,
  granted_scopes               text[] NOT NULL DEFAULT ARRAY[]::text[],
  input_fingerprint            char(64),
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT mcp_request_hash_ck CHECK (request_id_hash IS NULL OR request_id_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT mcp_input_hash_ck CHECK (input_fingerprint IS NULL OR input_fingerprint ~ '^[0-9a-f]{64}$'),
  CONSTRAINT mcp_tool_outcome_ck CHECK (outcome IN ('SUCCEEDED', 'FAILED', 'REJECTED', 'CANCELED')),
  CONSTRAINT mcp_tool_duration_ck CHECK (duration_ms IS NULL OR duration_ms >= 0),
  CONSTRAINT mcp_tool_finished_ck CHECK (finished_at IS NULL OR finished_at >= started_at),
  CONSTRAINT mcp_returned_row_bucket_ck
    CHECK (returned_row_bucket IS NULL OR returned_row_bucket IN ('0', '1-10', '11-50', '51-200', '201-1000', '1000+'))
);

COMMENT ON TABLE audit.mcp_tool_call IS 'Minimal observability only; do not store raw prompts, OAuth tokens, or full tool results.';

CREATE TABLE audit.user_action (
  user_action_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid REFERENCES app.app_user(user_id) ON DELETE SET NULL,
  action_type                  text NOT NULL,
  target_type                  text NOT NULL,
  target_id_hash               char(64),
  request_id_hash              char(64),
  outcome                      text NOT NULL,
  change_summary               jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT user_action_target_hash_ck CHECK (target_id_hash IS NULL OR target_id_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT user_action_request_hash_ck CHECK (request_id_hash IS NULL OR request_id_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT user_action_outcome_ck CHECK (outcome IN ('SUCCEEDED', 'FAILED', 'REJECTED'))
);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

CREATE VIEW market.v_active_transactions AS
SELECT *
FROM market.real_estate_transaction
WHERE record_status = 'VALID';

COMMENT ON VIEW market.v_active_transactions IS 'Default transaction view excluding canceled records.';

CREATE VIEW analytics.v_latest_metric_value AS
SELECT DISTINCT ON (
  s.scope_type,
  s.complex_id,
  s.region_id,
  s.area_type_id,
  md.metric_code
)
  s.scope_type,
  s.complex_id,
  s.region_id,
  s.area_type_id,
  s.area_min_m2,
  s.area_max_m2,
  s.as_of_date,
  s.window_start,
  s.window_end,
  s.formula_set_version,
  s.freshness_status,
  s.source_watermark_at,
  s.computed_at,
  md.metric_code,
  md.formula_version,
  md.unit,
  mv.status,
  mv.value_numeric,
  mv.value_text,
  mv.value_boolean,
  mv.value_date,
  mv.sample_count,
  mv.comparison_sample_count,
  mv.evidence
FROM analytics.analysis_snapshot s
JOIN analytics.metric_value mv ON mv.snapshot_id = s.snapshot_id
JOIN analytics.metric_definition md ON md.metric_definition_id = mv.metric_definition_id
ORDER BY
  s.scope_type,
  s.complex_id,
  s.region_id,
  s.area_type_id,
  md.metric_code,
  s.as_of_date DESC,
  s.computed_at DESC;

-- ---------------------------------------------------------------------------
-- Row-level security for OAuth-bound data
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;

ALTER TABLE app.app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.idempotency_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist_delivery_cursor ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.app_user FORCE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist FORCE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist_item FORCE ROW LEVEL SECURITY;
ALTER TABLE app.idempotency_record FORCE ROW LEVEL SECURITY;
ALTER TABLE app.watchlist_delivery_cursor FORCE ROW LEVEL SECURITY;

CREATE POLICY app_user_self_policy
  ON app.app_user
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

CREATE POLICY watchlist_owner_policy
  ON app.watchlist
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

CREATE POLICY watchlist_item_owner_policy
  ON app.watchlist_item
  USING (
    EXISTS (
      SELECT 1
      FROM app.watchlist w
      WHERE w.watchlist_id = watchlist_item.watchlist_id
        AND w.user_id = app.current_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM app.watchlist w
      WHERE w.watchlist_id = watchlist_item.watchlist_id
        AND w.user_id = app.current_user_id()
    )
  );

CREATE POLICY idempotency_owner_policy
  ON app.idempotency_record
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

CREATE POLICY watchlist_delivery_cursor_owner_policy
  ON app.watchlist_delivery_cursor
  USING (
    EXISTS (
      SELECT 1
      FROM app.watchlist w
      WHERE w.watchlist_id = watchlist_delivery_cursor.watchlist_id
        AND w.user_id = app.current_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM app.watchlist w
      WHERE w.watchlist_id = watchlist_delivery_cursor.watchlist_id
        AND w.user_id = app.current_user_id()
    )
  );

CREATE VIEW app.v_active_watchlist_item
WITH (security_invoker = true)
AS
SELECT
  wi.watchlist_item_id,
  wi.watchlist_id,
  wi.entity_type,
  wi.complex_id,
  wi.region_id,
  wi.area_type_id,
  wi.area_min_m2,
  wi.area_max_m2,
  wi.trade_types,
  wi.signal_rules,
  wi.label,
  wi.created_at,
  wi.updated_at
FROM app.watchlist_item wi
JOIN app.watchlist w ON w.watchlist_id = wi.watchlist_id
WHERE wi.deleted_at IS NULL
  AND wi.is_active
  AND w.deleted_at IS NULL
  AND w.is_active;

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX region_parent_level_idx ON ref.region (parent_region_id, region_level) WHERE is_active;
CREATE INDEX region_lawd_code5_idx ON ref.region (lawd_code5) WHERE lawd_code5 IS NOT NULL AND is_active;
CREATE INDEX region_full_path_trgm_idx ON ref.region USING gin (full_path gin_trgm_ops);
CREATE INDEX region_normalized_name_trgm_idx ON ref.region USING gin (normalized_name gin_trgm_ops);
CREATE INDEX region_alias_trgm_idx ON ref.region_alias USING gin (normalized_alias gin_trgm_ops);
CREATE INDEX source_link_lookup_idx ON ref.source_link_rule (source_id, entity_type, view_code, priority) WHERE is_active;

CREATE INDEX ingestion_run_dataset_started_idx ON ingest.ingestion_run (dataset_id, started_at DESC);
CREATE INDEX ingestion_run_region_month_idx ON ingest.ingestion_run (region_id, requested_contract_month, started_at DESC);
CREATE UNIQUE INDEX raw_record_run_source_key_uq ON ingest.raw_record (ingestion_run_id, source_record_key) WHERE source_record_key IS NOT NULL;
CREATE INDEX raw_record_dataset_key_idx ON ingest.raw_record (dataset_id, source_record_key) WHERE source_record_key IS NOT NULL;
CREATE INDEX raw_record_run_hash_idx ON ingest.raw_record (ingestion_run_id, source_record_hash);
CREATE INDEX raw_record_collected_brin_idx ON ingest.raw_record USING brin (collected_at);
CREATE INDEX raw_record_parse_status_idx ON ingest.raw_record (parse_status, collected_at);
CREATE INDEX partition_state_freshness_idx ON ingest.dataset_partition_state (freshness_status, updated_at DESC);
CREATE INDEX data_quality_open_idx ON ingest.data_quality_issue (severity, detected_at DESC) WHERE status IN ('OPEN', 'ACKNOWLEDGED');

CREATE INDEX complex_region_idx ON market.complex (primary_region_id, status);
CREATE INDEX complex_name_trgm_idx ON market.complex USING gin (normalized_name gin_trgm_ops);
CREATE INDEX complex_alias_trgm_idx ON market.complex_alias USING gin (normalized_alias gin_trgm_ops);
CREATE INDEX area_type_complex_area_idx ON market.area_type (complex_id, exclusive_area_m2) WHERE is_active;
CREATE INDEX external_entity_target_complex_idx ON market.external_entity_map (complex_id) WHERE complex_id IS NOT NULL;
CREATE INDEX external_entity_target_region_idx ON market.external_entity_map (region_id) WHERE region_id IS NOT NULL;

CREATE INDEX transaction_complex_date_active_idx
  ON market.real_estate_transaction (complex_id, contract_date DESC, transaction_id)
  WHERE record_status = 'VALID' AND complex_id IS NOT NULL;
CREATE INDEX transaction_region_date_active_idx
  ON market.real_estate_transaction (region_id, contract_date DESC, transaction_id)
  WHERE record_status = 'VALID';
CREATE INDEX transaction_complex_area_date_idx
  ON market.real_estate_transaction (complex_id, exclusive_area_m2, contract_date DESC)
  WHERE record_status = 'VALID' AND complex_id IS NOT NULL;
CREATE INDEX transaction_trade_date_idx
  ON market.real_estate_transaction (trade_type, contract_date DESC)
  WHERE record_status = 'VALID';
CREATE INDEX transaction_natural_hash_idx ON market.real_estate_transaction (dataset_id, natural_key_hash);
CREATE INDEX transaction_contract_date_brin_idx ON market.real_estate_transaction USING brin (contract_date);
CREATE INDEX transaction_collected_brin_idx ON market.real_estate_transaction USING brin (last_collected_at);
CREATE INDEX transaction_quality_flags_gin_idx ON market.real_estate_transaction USING gin (quality_flags);
CREATE INDEX transaction_revision_txn_idx ON market.transaction_revision (transaction_id, revision_no DESC);

CREATE INDEX analysis_snapshot_complex_idx ON analytics.analysis_snapshot (complex_id, as_of_date DESC, computed_at DESC) WHERE complex_id IS NOT NULL;
CREATE INDEX analysis_snapshot_region_idx ON analytics.analysis_snapshot (region_id, as_of_date DESC, computed_at DESC) WHERE region_id IS NOT NULL;
CREATE INDEX metric_value_definition_idx ON analytics.metric_value (metric_definition_id, computed_at DESC);
CREATE INDEX signal_active_complex_idx ON analytics.signal_event (complex_id, signal_type, started_at DESC) WHERE state IN ('STARTED', 'ACTIVE') AND complex_id IS NOT NULL;
CREATE INDEX signal_active_region_idx ON analytics.signal_event (region_id, signal_type, started_at DESC) WHERE state IN ('STARTED', 'ACTIVE') AND region_id IS NOT NULL;
CREATE INDEX ranking_entry_run_rank_idx ON analytics.ranking_entry (ranking_run_id, rank, complex_id);
CREATE INDEX entity_change_complex_time_idx ON analytics.entity_change_event (complex_id, occurred_at DESC) WHERE complex_id IS NOT NULL;
CREATE INDEX entity_change_region_time_idx ON analytics.entity_change_event (region_id, occurred_at DESC) WHERE region_id IS NOT NULL;

CREATE INDEX app_user_last_seen_idx ON app.app_user (last_seen_at DESC) WHERE status = 'ACTIVE';
CREATE INDEX watchlist_user_updated_idx ON app.watchlist (user_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX watchlist_item_watchlist_updated_idx ON app.watchlist_item (watchlist_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idempotency_expiry_idx ON app.idempotency_record (expires_at);

CREATE INDEX mcp_tool_call_started_brin_idx ON audit.mcp_tool_call USING brin (started_at);
CREATE INDEX mcp_tool_call_tool_outcome_idx ON audit.mcp_tool_call (tool_name, outcome, started_at DESC);
CREATE INDEX user_action_user_time_idx ON audit.user_action (user_id, occurred_at DESC) WHERE user_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Updated-at triggers
-- ---------------------------------------------------------------------------

CREATE TRIGGER data_source_set_updated_at
BEFORE UPDATE ON ref.data_source
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dataset_set_updated_at
BEFORE UPDATE ON ref.dataset
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER region_set_updated_at
BEFORE UPDATE ON ref.region
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER source_link_rule_set_updated_at
BEFORE UPDATE ON ref.source_link_rule
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER dataset_partition_state_set_updated_at
BEFORE UPDATE ON ingest.dataset_partition_state
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER complex_set_updated_at
BEFORE UPDATE ON market.complex
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER area_type_set_updated_at
BEFORE UPDATE ON market.area_type
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER external_entity_map_set_updated_at
BEFORE UPDATE ON market.external_entity_map
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER transaction_set_updated_at
BEFORE UPDATE ON market.real_estate_transaction
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER metric_definition_set_updated_at
BEFORE UPDATE ON analytics.metric_definition
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER signal_event_set_updated_at
BEFORE UPDATE ON analytics.signal_event
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER app_user_set_updated_at
BEFORE UPDATE ON app.app_user
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER watchlist_set_updated_at
BEFORE UPDATE ON app.watchlist
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER watchlist_item_set_updated_at
BEFORE UPDATE ON app.watchlist_item
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER watchlist_delivery_cursor_set_updated_at
BEFORE UPDATE ON app.watchlist_delivery_cursor
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ---------------------------------------------------------------------------
-- v3.0.0 AI Home Finder and listing link hub
-- ---------------------------------------------------------------------------

-- KR Apartment Market AI Skill v3.0.0
-- AI Home Finder and listing-link registry migration
-- PostgreSQL 16+


CREATE SCHEMA IF NOT EXISTS finder;
CREATE SCHEMA IF NOT EXISTS listing;

COMMENT ON SCHEMA finder IS 'User preference profiles, saved searches, recommendation runs, candidates, and explainable scores.';
COMMENT ON SCHEMA listing IS 'Policy-gated listing source registry, original-platform links, authorized observations, and duplicate clusters.';

CREATE TABLE IF NOT EXISTS finder.search_profile (
  search_profile_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  profile_key                  text NOT NULL,
  name                         text NOT NULL,
  schema_version               text NOT NULL DEFAULT '3.0.0',
  transaction_type             text NOT NULL,
  profile_document             jsonb NOT NULL,
  is_active                    boolean NOT NULL DEFAULT true,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at                   timestamptz,
  CONSTRAINT search_profile_user_key_uq UNIQUE (user_id, profile_key),
  CONSTRAINT search_profile_key_ck CHECK (profile_key ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
  CONSTRAINT search_profile_name_ck CHECK (char_length(name) BETWEEN 1 AND 120),
  CONSTRAINT search_profile_transaction_ck CHECK (transaction_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT')),
  CONSTRAINT search_profile_document_ck CHECK (jsonb_typeof(profile_document) = 'object')
);

CREATE TABLE IF NOT EXISTS finder.search_profile_version (
  search_profile_version_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  search_profile_id            uuid NOT NULL REFERENCES finder.search_profile(search_profile_id) ON DELETE CASCADE,
  version_number               integer NOT NULL,
  profile_document             jsonb NOT NULL,
  changed_by                   uuid REFERENCES app.app_user(user_id) ON DELETE SET NULL,
  change_reason                text,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT search_profile_version_uq UNIQUE (search_profile_id, version_number),
  CONSTRAINT search_profile_version_positive_ck CHECK (version_number >= 1),
  CONSTRAINT search_profile_version_document_ck CHECK (jsonb_typeof(profile_document) = 'object')
);

CREATE TABLE IF NOT EXISTS finder.saved_search (
  saved_search_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  search_profile_id            uuid NOT NULL REFERENCES finder.search_profile(search_profile_id) ON DELETE CASCADE,
  label                        text NOT NULL,
  date_from                    date,
  date_to                      date,
  candidate_limit              integer NOT NULL DEFAULT 20,
  notification_policy          jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active                    boolean NOT NULL DEFAULT true,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  deleted_at                   timestamptz,
  CONSTRAINT saved_search_label_ck CHECK (char_length(label) BETWEEN 1 AND 120),
  CONSTRAINT saved_search_dates_ck CHECK (date_from IS NULL OR date_to IS NULL OR date_from <= date_to),
  CONSTRAINT saved_search_limit_ck CHECK (candidate_limit BETWEEN 1 AND 100),
  CONSTRAINT saved_search_notification_ck CHECK (jsonb_typeof(notification_policy) = 'object')
);

CREATE TABLE IF NOT EXISTS finder.search_run (
  search_run_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  saved_search_id              uuid REFERENCES finder.saved_search(saved_search_id) ON DELETE CASCADE,
  search_profile_id            uuid NOT NULL REFERENCES finder.search_profile(search_profile_id) ON DELETE CASCADE,
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  status                       text NOT NULL DEFAULT 'RUNNING',
  scoring_model_version        text NOT NULL DEFAULT 'home-finder-3.0.0',
  metric_definition_version    text,
  requested_at                 timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at                 timestamptz,
  source_watermark_at          timestamptz,
  candidate_count              integer NOT NULL DEFAULT 0,
  excluded_candidate_count     integer NOT NULL DEFAULT 0,
  request_context              jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_code                   text,
  CONSTRAINT search_run_status_ck CHECK (status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')),
  CONSTRAINT search_run_counts_ck CHECK (candidate_count >= 0 AND excluded_candidate_count >= 0),
  CONSTRAINT search_run_context_ck CHECK (jsonb_typeof(request_context) = 'object'),
  CONSTRAINT search_run_completion_ck CHECK (
    (status = 'RUNNING' AND completed_at IS NULL)
    OR (status <> 'RUNNING' AND completed_at IS NOT NULL)
  )
);

CREATE TABLE IF NOT EXISTS finder.candidate_result (
  candidate_result_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  search_run_id                uuid NOT NULL REFERENCES finder.search_run(search_run_id) ON DELETE CASCADE,
  rank                         integer,
  lawd_code                    char(5) NOT NULL,
  region_name                  text,
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE SET NULL,
  complex_name                 text NOT NULL,
  transaction_type             text NOT NULL,
  match_score                  numeric(6,2) NOT NULL,
  confidence_score             numeric(6,2) NOT NULL,
  excluded                     boolean NOT NULL DEFAULT false,
  exclusion_reasons            text[] NOT NULL DEFAULT ARRAY[]::text[],
  facts                        jsonb NOT NULL,
  score_summary                jsonb NOT NULL,
  candidate_fingerprint        char(64) NOT NULL,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT candidate_result_run_fingerprint_uq UNIQUE (search_run_id, candidate_fingerprint),
  CONSTRAINT candidate_result_lawd_ck CHECK (lawd_code ~ '^\d{5}$'),
  CONSTRAINT candidate_result_rank_ck CHECK (rank IS NULL OR rank >= 1),
  CONSTRAINT candidate_result_transaction_ck CHECK (transaction_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT')),
  CONSTRAINT candidate_result_score_ck CHECK (match_score BETWEEN 0 AND 100 AND confidence_score BETWEEN 0 AND 100),
  CONSTRAINT candidate_result_facts_ck CHECK (jsonb_typeof(facts) = 'object'),
  CONSTRAINT candidate_result_summary_ck CHECK (jsonb_typeof(score_summary) = 'object'),
  CONSTRAINT candidate_result_fingerprint_ck CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS finder.candidate_score_component (
  candidate_score_component_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_result_id          uuid NOT NULL REFERENCES finder.candidate_result(candidate_result_id) ON DELETE CASCADE,
  component_code               text NOT NULL,
  component_score              numeric(6,2),
  component_weight             numeric(10,8) NOT NULL,
  available                    boolean NOT NULL,
  source_class                 text NOT NULL,
  explanation                  text NOT NULL,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT candidate_score_component_uq UNIQUE (candidate_result_id, component_code),
  CONSTRAINT candidate_component_code_ck CHECK (component_code ~ '^[a-z][a-z0-9_]{1,63}$'),
  CONSTRAINT candidate_component_score_ck CHECK (component_score IS NULL OR component_score BETWEEN 0 AND 100),
  CONSTRAINT candidate_component_weight_ck CHECK (component_weight BETWEEN 0 AND 1),
  CONSTRAINT candidate_component_source_ck CHECK (source_class IN (
    'MOLIT_TRANSACTION', 'DERIVED_METRIC', 'OPTIONAL_ENRICHMENT',
    'AUTHORIZED_LISTING_METADATA', 'USER_INPUT'
  ))
);

CREATE TABLE IF NOT EXISTS listing.source_registry (
  listing_source_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code                  text NOT NULL UNIQUE,
  display_name                 text NOT NULL,
  category                     text NOT NULL,
  homepage_url                 text NOT NULL,
  allowed_hosts                text[] NOT NULL,
  access_mode                  text NOT NULL DEFAULT 'LINK_OUT_ONLY',
  enabled                      boolean NOT NULL DEFAULT true,
  reviewed_at                  timestamptz,
  notes                        text,
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT listing_source_code_ck CHECK (source_code ~ '^[a-z][a-z0-9_]{1,63}$'),
  CONSTRAINT listing_source_category_ck CHECK (category IN (
    'RESIDENTIAL', 'APARTMENT_ANALYTICS', 'SMALL_RESIDENTIAL',
    'COMMERCIAL_LAND', 'LAND', 'AUCTION'
  )),
  CONSTRAINT listing_source_homepage_ck CHECK (homepage_url ~ '^https://'),
  CONSTRAINT listing_source_access_ck CHECK (access_mode IN (
    'LINK_OUT_ONLY', 'PUBLIC_DEEP_LINK', 'USER_SUPPLIED_URL',
    'AUTHORIZED_API', 'FIRST_PARTY_FEED'
  ))
);

CREATE TABLE IF NOT EXISTS listing.source_access_policy (
  listing_source_id            uuid PRIMARY KEY REFERENCES listing.source_registry(listing_source_id) ON DELETE CASCADE,
  allow_link_out               boolean NOT NULL DEFAULT true,
  allow_public_discovery       boolean NOT NULL DEFAULT false,
  allow_metadata_display       boolean NOT NULL DEFAULT false,
  allow_metadata_storage       boolean NOT NULL DEFAULT false,
  allow_description_storage    boolean NOT NULL DEFAULT false,
  allow_image_storage          boolean NOT NULL DEFAULT false,
  allow_contact_storage        boolean NOT NULL DEFAULT false,
  allow_automated_collection   boolean NOT NULL DEFAULT false,
  cache_ttl_seconds            integer,
  authorization_basis          text,
  terms_version                text,
  reviewed_at                  timestamptz,
  approved_by                  text,
  CONSTRAINT source_policy_cache_ck CHECK (cache_ttl_seconds IS NULL OR cache_ttl_seconds >= 0),
  CONSTRAINT source_policy_authorization_ck CHECK (
    NOT allow_automated_collection
    OR authorization_basis IS NOT NULL
  )
);

CREATE TABLE IF NOT EXISTS listing.discovery_link (
  discovery_link_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  candidate_result_id          uuid REFERENCES finder.candidate_result(candidate_result_id) ON DELETE CASCADE,
  listing_source_id            uuid NOT NULL REFERENCES listing.source_registry(listing_source_id) ON DELETE CASCADE,
  link_type                    text NOT NULL,
  target_url                   text NOT NULL,
  discovery_url                text,
  query_terms                  text,
  url_status                   text NOT NULL DEFAULT 'UNKNOWN',
  first_seen_at                timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_verified_at             timestamptz,
  removed_at                   timestamptz,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT discovery_link_type_ck CHECK (link_type IN (
    'PLATFORM_HOME', 'REGION_MAP', 'SITE_SEARCH', 'COMPLEX', 'LISTING', 'USER_SUPPLIED'
  )),
  CONSTRAINT discovery_link_target_ck CHECK (target_url ~ '^https://'),
  CONSTRAINT discovery_link_discovery_ck CHECK (discovery_url IS NULL OR discovery_url ~ '^https://'),
  CONSTRAINT discovery_link_status_ck CHECK (url_status IN (
    'ACTIVE', 'STALE', 'REMOVED', 'REDIRECTED', 'LOGIN_REQUIRED', 'UNKNOWN'
  )),
  CONSTRAINT discovery_link_metadata_ck CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE IF NOT EXISTS listing.user_supplied_url (
  user_supplied_url_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                      uuid NOT NULL REFERENCES app.app_user(user_id) ON DELETE CASCADE,
  listing_source_id            uuid REFERENCES listing.source_registry(listing_source_id) ON DELETE SET NULL,
  url_hash                     char(64) NOT NULL,
  encrypted_url                bytea NOT NULL,
  entity_type                  text NOT NULL DEFAULT 'PAGE',
  external_id                  text,
  consented_at                 timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_used_at                 timestamptz,
  expires_at                   timestamptz,
  deleted_at                   timestamptz,
  CONSTRAINT user_supplied_url_user_hash_uq UNIQUE (user_id, url_hash),
  CONSTRAINT user_supplied_url_hash_ck CHECK (url_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT user_supplied_url_entity_ck CHECK (entity_type IN ('PAGE', 'LISTING', 'COMPLEX', 'REGION')),
  CONSTRAINT user_supplied_url_expiry_ck CHECK (expires_at IS NULL OR expires_at > consented_at)
);

CREATE TABLE IF NOT EXISTS listing.listing_observation (
  listing_observation_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_source_id            uuid NOT NULL REFERENCES listing.source_registry(listing_source_id) ON DELETE CASCADE,
  external_listing_id          text NOT NULL,
  observed_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_verified_at             timestamptz,
  status                       text NOT NULL DEFAULT 'ACTIVE',
  lawd_code                    char(5),
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE SET NULL,
  complex_name                 text,
  transaction_type             text,
  price_10k_krw                numeric(16,2),
  deposit_10k_krw              numeric(16,2),
  monthly_rent_10k_krw         numeric(16,2),
  area_m2                      numeric(9,2),
  floor_label                  text,
  original_url                 text NOT NULL,
  metadata                     jsonb NOT NULL DEFAULT '{}'::jsonb,
  authorization_reference      text NOT NULL,
  removed_at                   timestamptz,
  CONSTRAINT listing_observation_source_external_uq UNIQUE (listing_source_id, external_listing_id, observed_at),
  CONSTRAINT listing_observation_status_ck CHECK (status IN ('ACTIVE', 'STALE', 'REMOVED', 'UNKNOWN')),
  CONSTRAINT listing_observation_lawd_ck CHECK (lawd_code IS NULL OR lawd_code ~ '^\d{5}$'),
  CONSTRAINT listing_observation_transaction_ck CHECK (transaction_type IS NULL OR transaction_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT')),
  CONSTRAINT listing_observation_prices_ck CHECK (
    (price_10k_krw IS NULL OR price_10k_krw >= 0)
    AND (deposit_10k_krw IS NULL OR deposit_10k_krw >= 0)
    AND (monthly_rent_10k_krw IS NULL OR monthly_rent_10k_krw >= 0)
  ),
  CONSTRAINT listing_observation_area_ck CHECK (area_m2 IS NULL OR area_m2 > 0),
  CONSTRAINT listing_observation_url_ck CHECK (original_url ~ '^https://'),
  CONSTRAINT listing_observation_metadata_ck CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE IF NOT EXISTS listing.listing_cluster (
  listing_cluster_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_fingerprint          char(64) NOT NULL UNIQUE,
  lawd_code                    char(5),
  complex_id                   uuid REFERENCES market.complex(complex_id) ON DELETE SET NULL,
  transaction_type             text,
  area_m2                      numeric(9,2),
  representative_price_10k_krw numeric(16,2),
  duplicate_confidence         numeric(5,4),
  created_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at                   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT listing_cluster_fingerprint_ck CHECK (cluster_fingerprint ~ '^[0-9a-f]{64}$'),
  CONSTRAINT listing_cluster_lawd_ck CHECK (lawd_code IS NULL OR lawd_code ~ '^\d{5}$'),
  CONSTRAINT listing_cluster_transaction_ck CHECK (transaction_type IS NULL OR transaction_type IN ('SALE', 'JEONSE', 'MONTHLY_RENT')),
  CONSTRAINT listing_cluster_confidence_ck CHECK (duplicate_confidence IS NULL OR duplicate_confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS listing.listing_cluster_member (
  listing_cluster_id           uuid NOT NULL REFERENCES listing.listing_cluster(listing_cluster_id) ON DELETE CASCADE,
  listing_observation_id       uuid NOT NULL REFERENCES listing.listing_observation(listing_observation_id) ON DELETE CASCADE,
  member_confidence            numeric(5,4) NOT NULL,
  added_at                     timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (listing_cluster_id, listing_observation_id),
  CONSTRAINT listing_cluster_member_confidence_ck CHECK (member_confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS listing.change_event (
  listing_change_event_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_source_id            uuid NOT NULL REFERENCES listing.source_registry(listing_source_id) ON DELETE CASCADE,
  external_listing_id          text NOT NULL,
  event_type                   text NOT NULL,
  occurred_at                  timestamptz NOT NULL DEFAULT clock_timestamp(),
  previous_value               jsonb,
  current_value                jsonb,
  candidate_result_id          uuid REFERENCES finder.candidate_result(candidate_result_id) ON DELETE SET NULL,
  CONSTRAINT listing_change_event_type_ck CHECK (event_type IN (
    'DISCOVERED', 'PRICE_CHANGED', 'STATUS_CHANGED', 'REMOVED', 'RESTORED', 'DUPLICATE_CLUSTER_CHANGED'
  )),
  CONSTRAINT listing_change_event_previous_ck CHECK (previous_value IS NULL OR jsonb_typeof(previous_value) = 'object'),
  CONSTRAINT listing_change_event_current_ck CHECK (current_value IS NULL OR jsonb_typeof(current_value) = 'object')
);


CREATE OR REPLACE FUNCTION listing.enforce_listing_observation_policy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  source_mode text;
  metadata_allowed boolean;
BEGIN
  SELECT r.access_mode, p.allow_metadata_storage
    INTO source_mode, metadata_allowed
  FROM listing.source_registry r
  JOIN listing.source_access_policy p
    ON p.listing_source_id = r.listing_source_id
  WHERE r.listing_source_id = NEW.listing_source_id
    AND r.enabled = true;

  IF source_mode IS NULL THEN
    RAISE EXCEPTION 'listing source is missing, disabled, or has no access policy';
  END IF;

  IF source_mode NOT IN ('AUTHORIZED_API', 'FIRST_PARTY_FEED')
     OR metadata_allowed IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'listing metadata storage is not authorized for source %', NEW.listing_source_id;
  END IF;

  IF NULLIF(btrim(NEW.authorization_reference), '') IS NULL THEN
    RAISE EXCEPTION 'authorization_reference is required for listing observations';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS enforce_listing_observation_policy
  ON listing.listing_observation;
CREATE TRIGGER enforce_listing_observation_policy
BEFORE INSERT OR UPDATE OF listing_source_id, authorization_reference
ON listing.listing_observation
FOR EACH ROW EXECUTE FUNCTION listing.enforce_listing_observation_policy();

CREATE INDEX IF NOT EXISTS search_profile_user_updated_idx
  ON finder.search_profile (user_id, updated_at DESC)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS saved_search_user_updated_idx
  ON finder.saved_search (user_id, updated_at DESC)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS search_run_profile_requested_idx
  ON finder.search_run (search_profile_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS candidate_result_run_rank_idx
  ON finder.candidate_result (search_run_id, excluded, rank);
CREATE INDEX IF NOT EXISTS candidate_result_complex_idx
  ON finder.candidate_result (lawd_code, lower(complex_name), created_at DESC);
CREATE INDEX IF NOT EXISTS discovery_link_candidate_idx
  ON listing.discovery_link (candidate_result_id, listing_source_id);
CREATE INDEX IF NOT EXISTS listing_observation_lookup_idx
  ON listing.listing_observation (listing_source_id, external_listing_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS listing_observation_complex_idx
  ON listing.listing_observation (complex_id, transaction_type, observed_at DESC)
  WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS listing_change_event_time_idx
  ON listing.change_event (listing_source_id, occurred_at DESC);

DROP TRIGGER IF EXISTS set_search_profile_updated_at ON finder.search_profile;
CREATE TRIGGER set_search_profile_updated_at
BEFORE UPDATE ON finder.search_profile
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
DROP TRIGGER IF EXISTS set_saved_search_updated_at ON finder.saved_search;
CREATE TRIGGER set_saved_search_updated_at
BEFORE UPDATE ON finder.saved_search
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
DROP TRIGGER IF EXISTS set_listing_source_updated_at ON listing.source_registry;
CREATE TRIGGER set_listing_source_updated_at
BEFORE UPDATE ON listing.source_registry
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
DROP TRIGGER IF EXISTS set_listing_cluster_updated_at ON listing.listing_cluster;
CREATE TRIGGER set_listing_cluster_updated_at
BEFORE UPDATE ON listing.listing_cluster
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE finder.search_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE finder.search_profile_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE finder.saved_search ENABLE ROW LEVEL SECURITY;
ALTER TABLE finder.search_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE finder.candidate_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE finder.candidate_score_component ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing.discovery_link ENABLE ROW LEVEL SECURITY;
ALTER TABLE listing.user_supplied_url ENABLE ROW LEVEL SECURITY;

ALTER TABLE finder.search_profile FORCE ROW LEVEL SECURITY;
ALTER TABLE finder.search_profile_version FORCE ROW LEVEL SECURITY;
ALTER TABLE finder.saved_search FORCE ROW LEVEL SECURITY;
ALTER TABLE finder.search_run FORCE ROW LEVEL SECURITY;
ALTER TABLE finder.candidate_result FORCE ROW LEVEL SECURITY;
ALTER TABLE finder.candidate_score_component FORCE ROW LEVEL SECURITY;
ALTER TABLE listing.discovery_link FORCE ROW LEVEL SECURITY;
ALTER TABLE listing.user_supplied_url FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS search_profile_owner_policy ON finder.search_profile;
CREATE POLICY search_profile_owner_policy ON finder.search_profile
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

DROP POLICY IF EXISTS search_profile_version_owner_policy ON finder.search_profile_version;
CREATE POLICY search_profile_version_owner_policy ON finder.search_profile_version
  USING (EXISTS (
    SELECT 1 FROM finder.search_profile p
    WHERE p.search_profile_id = search_profile_version.search_profile_id
      AND p.user_id = app.current_user_id()
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM finder.search_profile p
    WHERE p.search_profile_id = search_profile_version.search_profile_id
      AND p.user_id = app.current_user_id()
  ));

DROP POLICY IF EXISTS saved_search_owner_policy ON finder.saved_search;
CREATE POLICY saved_search_owner_policy ON finder.saved_search
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

DROP POLICY IF EXISTS search_run_owner_policy ON finder.search_run;
CREATE POLICY search_run_owner_policy ON finder.search_run
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

DROP POLICY IF EXISTS candidate_result_owner_policy ON finder.candidate_result;
CREATE POLICY candidate_result_owner_policy ON finder.candidate_result
  USING (EXISTS (
    SELECT 1 FROM finder.search_run r
    WHERE r.search_run_id = candidate_result.search_run_id
      AND r.user_id = app.current_user_id()
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM finder.search_run r
    WHERE r.search_run_id = candidate_result.search_run_id
      AND r.user_id = app.current_user_id()
  ));

DROP POLICY IF EXISTS candidate_score_component_owner_policy ON finder.candidate_score_component;
CREATE POLICY candidate_score_component_owner_policy ON finder.candidate_score_component
  USING (EXISTS (
    SELECT 1
    FROM finder.candidate_result c
    JOIN finder.search_run r ON r.search_run_id = c.search_run_id
    WHERE c.candidate_result_id = candidate_score_component.candidate_result_id
      AND r.user_id = app.current_user_id()
  ))
  WITH CHECK (EXISTS (
    SELECT 1
    FROM finder.candidate_result c
    JOIN finder.search_run r ON r.search_run_id = c.search_run_id
    WHERE c.candidate_result_id = candidate_score_component.candidate_result_id
      AND r.user_id = app.current_user_id()
  ));

DROP POLICY IF EXISTS discovery_link_owner_policy ON listing.discovery_link;
CREATE POLICY discovery_link_owner_policy ON listing.discovery_link
  USING (user_id IS NULL OR user_id = app.current_user_id())
  WITH CHECK (user_id IS NULL OR user_id = app.current_user_id());

DROP POLICY IF EXISTS user_supplied_url_owner_policy ON listing.user_supplied_url;
CREATE POLICY user_supplied_url_owner_policy ON listing.user_supplied_url
  USING (user_id = app.current_user_id())
  WITH CHECK (user_id = app.current_user_id());

INSERT INTO listing.source_registry (
  source_code, display_name, category, homepage_url, allowed_hosts,
  access_mode, enabled, reviewed_at, notes
)
VALUES
  ('naver', '네이버 부동산', 'RESIDENTIAL', 'https://fin.land.naver.com/', ARRAY['fin.land.naver.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '원문 링크만 제공'),
  ('daangn', '당근 부동산', 'RESIDENTIAL', 'https://realty.daangn.com/', ARRAY['realty.daangn.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '지역 지도와 원문 링크 제공'),
  ('peterpan', '피터팬의 좋은방 구하기', 'RESIDENTIAL', 'https://www.peterpanz.com/', ARRAY['www.peterpanz.com','peterpanz.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '원문 링크만 제공'),
  ('asil', '아실', 'APARTMENT_ANALYTICS', 'https://asil.kr/asil/index.jsp', ARRAY['asil.kr','www.asil.kr'], 'LINK_OUT_ONLY', true, '2026-08-26', '단지 분석 원문 링크'),
  ('kb', 'KB부동산', 'RESIDENTIAL', 'https://kbland.kr/', ARRAY['kbland.kr','www.kbland.kr'], 'LINK_OUT_ONLY', true, '2026-08-26', '시세·매물 원문 링크'),
  ('dabang', '다방', 'SMALL_RESIDENTIAL', 'https://www.dabangapp.com/', ARRAY['www.dabangapp.com','dabangapp.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '소형 주거 원문 링크'),
  ('zigbang', '직방', 'RESIDENTIAL', 'https://www.zigbang.com/', ARRAY['www.zigbang.com','zigbang.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '주거 원문 링크'),
  ('disco', '디스코', 'COMMERCIAL_LAND', 'https://disco.re/', ARRAY['disco.re','www.disco.re'], 'LINK_OUT_ONLY', true, '2026-08-26', '토지·건물 원문 링크'),
  ('valuemap', '밸류맵', 'COMMERCIAL_LAND', 'https://www.valueupmap.com/', ARRAY['www.valueupmap.com','valueupmap.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '토지·건물 원문 링크'),
  ('ddangya', '땅야', 'LAND', 'https://ddangya.com/', ARRAY['ddangya.com','www.ddangya.com'], 'LINK_OUT_ONLY', true, '2026-08-26', '토지 원문 링크'),
  ('onbid', '온비드', 'AUCTION', 'https://www.onbid.co.kr/', ARRAY['www.onbid.co.kr','onbid.co.kr'], 'LINK_OUT_ONLY', true, '2026-08-26', '공매 원문 링크')
ON CONFLICT (source_code) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  category = EXCLUDED.category,
  homepage_url = EXCLUDED.homepage_url,
  allowed_hosts = EXCLUDED.allowed_hosts,
  access_mode = EXCLUDED.access_mode,
  enabled = EXCLUDED.enabled,
  reviewed_at = EXCLUDED.reviewed_at,
  notes = EXCLUDED.notes;

INSERT INTO listing.source_access_policy (
  listing_source_id, allow_link_out, allow_public_discovery,
  allow_metadata_display, allow_metadata_storage, allow_description_storage,
  allow_image_storage, allow_contact_storage, allow_automated_collection,
  cache_ttl_seconds, authorization_basis, terms_version, reviewed_at
)
SELECT
  listing_source_id,
  true,
  source_code = 'daangn',
  false,
  false,
  false,
  false,
  false,
  false,
  NULL,
  'Public original-platform link only; no ingestion authorization recorded',
  NULL,
  '2026-08-26'
FROM listing.source_registry
ON CONFLICT (listing_source_id) DO UPDATE SET
  allow_link_out = EXCLUDED.allow_link_out,
  allow_public_discovery = EXCLUDED.allow_public_discovery,
  allow_metadata_display = EXCLUDED.allow_metadata_display,
  allow_metadata_storage = EXCLUDED.allow_metadata_storage,
  allow_description_storage = EXCLUDED.allow_description_storage,
  allow_image_storage = EXCLUDED.allow_image_storage,
  allow_contact_storage = EXCLUDED.allow_contact_storage,
  allow_automated_collection = EXCLUDED.allow_automated_collection,
  cache_ttl_seconds = EXCLUDED.cache_ttl_seconds,
  authorization_basis = EXCLUDED.authorization_basis,
  reviewed_at = EXCLUDED.reviewed_at;

COMMIT;
