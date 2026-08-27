# KR Apartment Market 데이터베이스 설계 v3.0.0

- 데이터베이스: PostgreSQL 16+
- 통합 DDL: `database/schema.sql`
- v2 runtime migration: `database/migrations/002_real_estate_mcp_integration.sql`
- v3 Home Finder migration: `database/migrations/003_home_finder.sql`
- 기준일: 2026-08-26

## 1. 설계 목표

1. 공공 API 원본·정규화 거래·파생 지표를 분리합니다.
2. 취소·정정 이력을 물리 삭제 없이 보존합니다.
3. 단지와 면적 타입을 안정적 ID로 관리합니다.
4. 산식·추천 모델 버전을 저장합니다.
5. 사용자 검색 프로필과 추천 실행을 재현합니다.
6. 광고매물 원천별 접근 권한을 데이터 수준에서 통제합니다.
7. 승인 없는 매물 metadata·사진·연락처 저장을 차단합니다.
8. 사용자별 RLS와 최소 감사 로그를 적용합니다.

## 2. schema map

```text
ref        데이터 원천·데이터셋·지역·검증된 원문 링크
ingest     수집 실행·원본 레코드·watermark·품질 이슈
market     단지·면적 타입·현재 거래·revision·외부 ID
analytics  metric definition·snapshot·signal·ranking·change event
app        사용자·관심 목록·idempotency·delivery cursor
audit      MCP 호출·사용자 쓰기 감사
finder     검색 프로필·버전·저장 검색·추천 실행·candidate score
listing    광고매물 원천 registry·정책·링크·승인 observation·cluster
```

## 3. v3 엔티티 흐름

```text
app.app_user
  └─ finder.search_profile
       ├─ finder.search_profile_version
       └─ finder.saved_search
            └─ finder.search_run
                 └─ finder.candidate_result
                      └─ finder.candidate_score_component

listing.source_registry
  └─ listing.source_access_policy
       ├─ listing.discovery_link
       ├─ listing.user_supplied_url
       └─ listing.listing_observation (AUTHORIZED_API/FIRST_PARTY_FEED only)
```

## 4. finder schema

### `finder.search_profile`

사용자별 canonical profile의 현재 버전입니다.

주요 필드:

```text
profile_key
name
schema_version
transaction_type
profile_document jsonb
is_active
created_at / updated_at / deleted_at
```

### `finder.search_profile_version`

변경 전후 프로필을 버전별로 보존합니다. 동일 profile에서 version number는 유일합니다.

### `finder.saved_search`

반복 실행 설정을 저장합니다.

```text
date_from / date_to
candidate_limit
notification_policy
```

### `finder.search_run`

각 추천 실행의 상태와 모델 버전, source watermark, 후보 수를 기록합니다.

```text
RUNNING
SUCCEEDED
PARTIAL
FAILED
```

### `finder.candidate_result`

한 실행에서 한 후보의 facts와 점수 요약을 저장합니다.

- `match_score`와 `confidence_score` 분리
- excluded 여부와 이유
- fingerprint로 동일 실행 중복 방지
- 공공 단지 master와 매핑되지 않아도 raw name 보존

### `finder.candidate_score_component`

점수 구성 요소별 score, weight, availability, source class, explanation을 저장합니다.

허용 source class:

```text
MOLIT_TRANSACTION
DERIVED_METRIC
OPTIONAL_ENRICHMENT
AUTHORIZED_LISTING_METADATA
USER_INPUT
```

## 5. listing schema

### `listing.source_registry`

플랫폼의 source code, 공식 homepage, allowed host, category와 access mode를 저장합니다.

### `listing.source_access_policy`

기본값:

```text
allow_link_out              true
allow_public_discovery      source별 제한
allow_metadata_display      false
allow_metadata_storage      false
allow_description_storage   false
allow_image_storage         false
allow_contact_storage       false
allow_automated_collection  false
```

### `listing.discovery_link`

추천 후보에 대해 생성한 원문 홈·지역 지도·discovery URL과 생성 context를 저장합니다. 페이지 content는 저장하지 않습니다.

### `listing.user_supplied_url`

사용자가 제공한 URL의 source classification과 상태만 저장합니다. URL 원문은 tenant 정책에 따라 암호화·해시·삭제 기간을 적용할 수 있습니다.

### `listing.listing_observation`

공식 API·제휴 피드·first-party feed가 있을 때만 사용합니다. access policy가 허용하는 필드만 저장합니다.

### `listing.listing_cluster`

허가된 metadata가 충분할 때 플랫폼 간 중복 후보를 묶습니다. 불확실한 자동 병합은 금지합니다.

## 6. 거래 저장

### 원본과 정규화

```text
ingest.raw_record
→ parser/resolver
→ market.real_estate_transaction
→ market.transaction_revision
```

### 식별자

- source record key: 데이터셋 내 결정적 ID
- natural key hash: 정합성 점검용, non-unique
- 동일 조건 실제 복수 거래를 삭제하지 않음

### 상태

```text
VALID
CANCELED
```

기본 조회 view는 `VALID`만 반환합니다.

## 7. 분석 저장

```text
analytics.metric_definition
→ analytics.analysis_snapshot
→ analytics.metric_value
```

metric value는 `null`과 0을 구분합니다. 산식 변경은 기존 row 수정이 아니라 새 formula version을 추가합니다.

## 8. RLS

다음 사용자 데이터에는 RLS와 `FORCE ROW LEVEL SECURITY`를 적용합니다.

```text
app.app_user
app.watchlist
app.watchlist_item
finder.search_profile
finder.saved_search
finder.search_run
```

애플리케이션은 tenant/user context를 transaction local setting으로 주입합니다.

## 9. 인덱스

주요 인덱스:

- region × contract date × property/trade type
- complex × area × contract date
- profile user × active
- saved search user × active
- search run profile × requested_at
- candidate result run × rank
- listing source code
- listing URL hash
- change event dedup key

## 10. migration 적용

신규 설치:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/seed.sql
```

v2 운영 DB:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f database/migrations/003_home_finder.sql
```

운영 적용 전 snapshot backup과 staging migration을 수행합니다.

## 11. 정책 invariant

1. `LINK_OUT_ONLY` source에 metadata observation을 기록하지 않습니다.
2. 이미지·연락처 flag는 별도 승인 없이 true가 될 수 없습니다.
3. candidate score는 0~100입니다.
4. component weight는 0~1입니다.
5. 프로필 document는 JSON object입니다.
6. API key, cookie, raw Authorization header는 어떤 테이블에도 저장하지 않습니다.
7. user-facing delete는 soft delete 또는 정책상 완전 삭제를 지원합니다.
