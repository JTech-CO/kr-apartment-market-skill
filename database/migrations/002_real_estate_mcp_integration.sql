BEGIN;

CREATE SCHEMA IF NOT EXISTS public_api;

CREATE TABLE IF NOT EXISTS public_api.request_cache (
    request_cache_id bigserial PRIMARY KEY,
    source_code text NOT NULL,
    endpoint_code text NOT NULL,
    lawd_code varchar(5),
    deal_month char(6),
    page_no integer NOT NULL DEFAULT 1 CHECK (page_no > 0),
    request_fingerprint text NOT NULL UNIQUE,
    response_status integer,
    total_count integer,
    payload_sha256 char(64),
    collected_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);

CREATE INDEX IF NOT EXISTS request_cache_lookup_idx
    ON public_api.request_cache (source_code, endpoint_code, lawd_code, deal_month, page_no);

CREATE TABLE IF NOT EXISTS public_api.subscription_notice (
    notice_id text PRIMARY KEY,
    house_name text NOT NULL,
    address text,
    announcement_date date,
    application_start_date date,
    application_end_date date,
    winner_announcement_date date,
    contract_start_date date,
    contract_end_date date,
    source_payload jsonb NOT NULL,
    collected_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public_api.subscription_stat_snapshot (
    snapshot_id bigserial PRIMARY KEY,
    stat_kind text NOT NULL,
    stat_year_month char(6),
    area_code text,
    payload jsonb NOT NULL,
    collected_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON SCHEMA public_api IS
    'Optional cache and normalized ApplyHome data for the integrated public-data runtime.';

COMMIT;
