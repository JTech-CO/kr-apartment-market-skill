-- KR Apartment Market AI Skill v3.0.0
-- AI Home Finder and listing-link registry migration
-- PostgreSQL 16+

BEGIN;

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
