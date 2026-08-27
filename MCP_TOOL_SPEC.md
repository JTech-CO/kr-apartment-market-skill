# MCP 도구 명세 — KR Apartment Market AI Skill v3.0.0

문서 버전: 3.0.0  
대상 프로토콜: MCP `2026-07-28`  
JSON Schema: Draft 2020-12  
기본 시간대: `Asia/Seoul`

## 1. 범위

단일 FastMCP 서버가 다음을 제공합니다.

```text
kr_apartment.*  17개
kr_home.*       15개
--------------------
canonical       32개

vendored compatibility 16개 (선택)
integrated total       48개
```

기계 판독 가능한 전체 입력·출력 schema는 `mcp/tool-definitions.json`이 기준입니다. 이 문서는 의미, 호출 순서, 정책과 오류 계약을 정의합니다.

## 2. 전송

### stdio

로컬 Claude Desktop, Codex CLI, 기타 MCP client에 권장합니다.

```bash
uv run kr-apartment-market --transport stdio
```

### Streamable HTTP

```bash
uv run kr-apartment-market \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8765
```

공개 배포에서는 TLS reverse proxy, 인증, rate limit과 origin 정책을 별도로 구성합니다.

## 3. 인증

### 원천 API

```text
DATA_GO_KR_API_KEY
ODCLOUD_API_KEY 또는 ODCLOUD_SERVICE_KEY
```

API key는 MCP 응답·로그·프로필 저장소에 포함하지 않습니다.

### 사용자 데이터

개인용 런타임은 로컬 JSON 파일을 사용합니다. 다중 사용자 운영형은 OAuth와 PostgreSQL RLS를 적용해야 합니다.

## 4. 공통 응답 원칙

Canonical 도구는 가능한 경우 구조화 결과를 반환하며, 다음 의미를 유지합니다.

```text
request_id        요청 추적 ID
answered_at       응답 생성 시각
source            데이터 원천
source_months     조회한 계약월
collected_at      수집 시각
warnings          데이터 품질·부분 실패
```

`null`과 0을 구분합니다.

```text
null = 데이터 없음 또는 계산 불가
0    = 실제 값이 0
```

## 5. 도구 그룹

### 5.1 지역·거래·단지

| Tool | 역할 |
|---|---|
| `kr_apartment.resolve_location` | 지역명·단지명 후보 해석 |
| `kr_apartment.get_transactions` | 정규화 실거래 조회 |
| `kr_apartment.search_complexes` | 거래 데이터 안의 단지 검색 |
| `kr_apartment.get_complex_snapshot` | 단지 가격·거래량·전세 지표 |
| `kr_apartment.compare_complexes` | 동일 기준 복수 단지 비교 |

### 5.2 지역 시장·신호

| Tool | 역할 |
|---|---|
| `kr_apartment.get_region_pulse` | 지역 시장 펄스 |
| `kr_apartment.rank_complexes` | 지표별 단지 순위 |
| `kr_apartment.get_signal_feed` | 신고가·거래 재개 등 신호 |
| `kr_apartment.get_data_freshness` | 원천 데이터 신선도 |
| `kr_apartment.get_source_link` | 공공·Apt2Me 등 원문 링크 |

### 5.3 계산·관심 단지

| Tool | 역할 |
|---|---|
| `kr_apartment.calculate_loan_payment` | 원리금 균등상환 계산 |
| `kr_apartment.calculate_compound_growth` | 복리 성장 계산 |
| `kr_apartment.calculate_monthly_cashflow` | 월 현금흐름 계산 |
| `kr_apartment.get_watchlist` | 관심 단지 조회 |
| `kr_apartment.upsert_watchlist_item` | 관심 단지 등록·수정 |
| `kr_apartment.delete_watchlist_item` | 관심 단지 삭제 |
| `kr_apartment.get_watchlist_brief` | 관심 단지 변경 브리핑 |

### 5.4 Home Finder 프로필

| Tool | 역할 |
|---|---|
| `kr_home.validate_search_profile` | 입력 조건 검증·정규화 |
| `kr_home.create_search_profile` | 프로필 영속 저장 |
| `kr_home.get_search_profile` | 프로필 조회 |
| `kr_home.update_search_profile` | patch 후 전체 재검증 |
| `kr_home.delete_search_profile` | 프로필 삭제 |

### 5.5 Home Finder 추천

| Tool | 역할 |
|---|---|
| `kr_home.recommend_complexes` | 공공 실거래 기반 후보 생성·점수화 |
| `kr_home.explain_complex_match` | 한 후보의 점수·근거 설명 |
| `kr_home.compare_candidates` | 복수 후보 점수 구성 비교 |

### 5.6 광고매물 링크

| Tool | 역할 |
|---|---|
| `kr_home.find_listing_links` | 원천별 공식 홈·지역·discovery 링크 생성 |
| `kr_home.get_listing_source_capabilities` | 원천 정책·지원 유형 확인 |
| `kr_home.inspect_listing_url` | 사용자 URL을 fetch 없이 source 분류 |

### 5.7 저장 검색

| Tool | 역할 |
|---|---|
| `kr_home.save_search` | 프로필 기반 저장 검색 생성 |
| `kr_home.get_saved_searches` | 저장 검색 목록 |
| `kr_home.delete_saved_search` | 저장 검색 삭제 |
| `kr_home.get_search_updates` | 새 추천 실행과 이전 결과 diff |

## 6. Home Finder 핵심 계약

### 6.1 Search Profile

최소 입력 예:

```json
{
  "transaction_type": "sale",
  "property_types": ["apartment"],
  "lawd_codes": ["41465", "41135"],
  "budget": {
    "max_price_10k_krw": 90000
  },
  "area": {
    "min_m2": 74,
    "max_m2": 86,
    "tolerance_m2": 1
  },
  "building": {
    "max_age_years": 20
  },
  "hard_constraints": {
    "min_transaction_count": 3
  },
  "unknown_policy": "neutral",
  "listing_sources": ["naver", "daangn", "peterpan", "asil", "kb"]
}
```

정규화 결과는 `profile_id`, `schema_version`, timestamps, 정규화한 weights를 추가합니다.

### 6.2 Candidate Facts

```json
{
  "lawd_code": "41465",
  "region_name": "경기도 용인시 수지구",
  "complex_name": "예시단지",
  "transaction_type": "sale",
  "reference_price_10k_krw": 75500,
  "latest_contract_date": "2026-08-03",
  "transaction_count": 6,
  "area_min_m2": 84.8,
  "area_max_m2": 84.99,
  "representative_build_year": 2015,
  "recovery_rate_pct": 91.5,
  "source_months": ["202607", "202608"],
  "enrichment": {}
}
```

### 6.3 Candidate Score

```json
{
  "match_score": 87.6,
  "confidence_score": 78.0,
  "excluded": false,
  "exclusion_reasons": [],
  "components": [],
  "strengths": [],
  "tradeoffs": [],
  "unknowns": [],
  "available_weight": 0.82,
  "total_weight": 1.0
}
```

### 6.4 Listing Link

```json
{
  "source_id": "daangn",
  "source_name": "당근 부동산",
  "access_mode": "LINK_OUT_ONLY",
  "link_type": "REGION_MAP",
  "url": "https://realty.daangn.com/map/...",
  "metadata_available": false,
  "policy_note": "원문에서 현재 광고 상태를 확인해야 합니다."
}
```

## 7. 추천 호출 순서

### 일회성 탐색

```text
resolve_location
→ validate_search_profile
→ recommend_complexes
→ explain_complex_match (선택)
→ get_complex_snapshot (선택)
```

### 반복 탐색

```text
validate_search_profile
→ create_search_profile
→ save_search
→ get_search_updates
```

### 사용자 제공 매물 URL

```text
inspect_listing_url
→ get_complex_snapshot 또는 get_transactions
→ 사용자가 제공한 광고 정보와 수동 비교
```

v3 기본 도구는 URL 페이지 내용을 자동 추출하지 않습니다.

## 8. Link Source Capability

원천 capability는 최소 다음 필드를 포함합니다.

```text
source_id
name
homepage
domains
category
access_mode
supports_user_supplied_url
supported_property_types
allow_metadata_display
allow_metadata_storage
allow_image_storage
allow_contact_storage
```

기본 registry에서는 모든 저장·재표시 flag가 false입니다.

## 9. 저장 검색 diff

변경 event 예:

```text
CANDIDATE_ADDED
CANDIDATE_REMOVED
RANK_CHANGED
REFERENCE_PRICE_CHANGED
TRANSACTION_COUNT_CHANGED
NO_BASELINE
NO_CHANGE
```

가격 변화는 동일 거래 유형과 동일 candidate key에서만 비교합니다.

## 10. 오류 모델

도구는 예외 stack trace 대신 구조화 오류를 반환해야 합니다.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "area.min_m2 must not exceed area.max_m2",
    "retryable": false,
    "source": null
  }
}
```

주요 코드:

| Code | 의미 | 재시도 |
|---|---|---:|
| `VALIDATION_ERROR` | 입력 오류 | 아니오 |
| `NOT_FOUND` | 프로필·검색·단지 없음 | 아니오 |
| `AMBIGUOUS_LOCATION` | 지역 후보 복수 | 사용자 선택 |
| `CONFIG_ERROR` | API key 등 설정 없음 | 설정 후 |
| `SOURCE_TIMEOUT` | 외부 원천 timeout | 예 |
| `SOURCE_RATE_LIMITED` | 호출 한도 | 나중에 |
| `PARTIAL_RESULT` | 일부 지역·원천 성공 | 선택 |
| `UNSUPPORTED_SOURCE` | registry에 없는 원천 | 아니오 |
| `POLICY_DENIED` | 허용되지 않은 데이터 작업 | 아니오 |

## 11. Tool Annotation

- 조회·검증·계산: read-only, non-destructive
- create/update: write, idempotency 고려
- delete profile/search/watchlist: destructive
- 외부 링크 생성: network fetch 없음
- 실제 공공 API 조회: open-world effect

## 12. 페이지네이션과 제한

공공 API adapter:

```text
page size 기본 1000
max pages 기본 50
max months 기본 60
external concurrency 기본 4
```

Home Finder:

```text
max lawd codes 20
candidate limit 기본 20, 최대 100
listing sources registry 내 값만 허용
```

## 13. 정책 강제

MCP layer는 다음을 허용하지 않습니다.

- 제3자 플랫폼 로그인 cookie 입력
- 광고 페이지를 fetch하는 generic URL tool
- 승인 없는 listing metadata 저장
- 사진·연락처 저장
- AI가 계산한 비재현 점수를 canonical score로 저장

## 14. 호환 계층

`ENABLE_REAL_ESTATE_MCP_COMPAT=true`일 때 16개 호환 도구를 추가합니다. 호환 도구의 이름과 단순 월별 API 형태는 기존 클라이언트 이전을 위한 것이며, 신규 구현은 범위·최신성·정규화·정책이 강화된 canonical 도구를 사용해야 합니다.

## 15. 검증

```bash
python scripts/generate_tool_catalog.py
python scripts/validate_package.py . --write-manifest
pytest
```

validator는 catalog와 runtime 이름, 32/48 도구 수, v3 필수 파일, source policy, Python compile과 라이선스 고지를 확인합니다.
