# AI Home Finder 시스템 아키텍처

문서 버전: 3.0.0  
기준일: 2026-08-26

## 1. 목표

v3.0.0은 다음 두 영역을 분리하면서 하나의 사용자 경험으로 결합합니다.

1. **추천·분석 계층**: 공공데이터를 근거로 독립적으로 동작
2. **광고매물 탐색 계층**: 원문 플랫폼 링크 또는 승인된 피드만 사용

이 분리는 제3자 플랫폼 장애·URL 변경·권한 변경이 단지 추천 엔진까지 중단시키는 것을 방지합니다.

## 2. 논리 구조

```text
┌──────────────────────────────────────────────────────────────┐
│                     MCP Client / AI Agent                    │
│ ChatGPT · Codex · Claude Code · Custom Agent · Web App       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│             KR Apartment Market AI Skill v3.0.0              │
│                                                              │
│ Intent Router                                                │
│ ├─ 시장 조회 → kr_apartment.*                                │
│ └─ 주택 탐색 → kr_home.*                                     │
│                                                              │
│ Response Policy                                              │
│ ├─ 사실 / 지표 / 해석 분리                                   │
│ ├─ 실거래 / 호가 분리                                        │
│ ├─ 적합도 / 신뢰도 분리                                      │
│ └─ 미확인 데이터 명시                                        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                      Unified FastMCP                         │
│                                                              │
│ Market Tools (17)             Home Finder Tools (15)          │
│ ├─ location                   ├─ profile                      │
│ ├─ transactions               ├─ recommendation               │
│ ├─ snapshot/ranking           ├─ explanation                  │
│ ├─ finance                    ├─ listing links                │
│ └─ watchlist                  └─ saved searches               │
└───────────────┬───────────────────────────────┬──────────────┘
                │                               │
                ▼                               ▼
┌────────────────────────────┐    ┌─────────────────────────────┐
│ Public Data Layer          │    │ Listing Link Layer          │
│ ├─ MOLIT RTMS APIs         │    │ ├─ Source Registry          │
│ ├─ ApplyHome / ODCloud     │    │ ├─ Policy Gate              │
│ ├─ Region Code Resource    │    │ ├─ Link Resolver            │
│ └─ Normalization           │    │ └─ User URL Classifier      │
└───────────────┬────────────┘    └──────────────┬──────────────┘
                │                                │
                ▼                                ▼
┌────────────────────────────┐    ┌─────────────────────────────┐
│ Recommendation Engine      │    │ Original Platforms          │
│ ├─ Candidate Builder       │    │ Naver · Daangn · Peterpan   │
│ ├─ Hard Constraint Filter  │    │ Asil · KB · additional      │
│ ├─ Deterministic Scoring   │    │                             │
│ ├─ Confidence Estimator    │    │ No central scraping by      │
│ └─ Explanation Generator   │    │ default                     │
└───────────────┬────────────┘    └─────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ Persistence                                                   │
│ Personal: Atomic JSON                                         │
│ Service: PostgreSQL finder/listing + existing market schemas  │
└──────────────────────────────────────────────────────────────┘
```

## 3. 런타임 구성 요소

### 3.1 Search Profile Validator

자연어에서 추출된 JSON을 다음 canonical profile로 정규화합니다.

```json
{
  "profile_id": "...",
  "schema_version": "3.0.0",
  "transaction_type": "sale",
  "property_types": ["apartment"],
  "lawd_codes": ["41465", "41135"],
  "budget": {"max_price_10k_krw": 90000},
  "area": {"min_m2": 74, "max_m2": 86},
  "building": {"max_age_years": 20},
  "weights": {},
  "unknown_policy": "neutral",
  "listing_sources": ["naver", "daangn", "peterpan", "asil", "kb"]
}
```

Validator는 단위, 범위, 열거형, 가중치, 법정동 코드, 최대 지역 수와 후보 수를 제한합니다.

### 3.2 Candidate Builder

- 지정 기간의 매매·임대차 거래를 병렬 조회
- 취소 거래 제외
- 단지명 정규화
- 거래 유형별 기준 가격 산출
- 면적·준공연도·최근 계약일·표본 수 집계
- 기존 시장 지표 엔진으로 회복률·전세가율·추정 갭 산출

### 3.3 Constraint Filter

필수 조건은 점수 감점이 아니라 후보 제외로 처리합니다.

```text
예산 상한 초과
희망 면적과 거래 면적 비중첩
최대 건물 연식 초과
최소 거래 표본 미달
명시된 주차·통근 필수 조건 위반
```

미확인 값의 처리 방식은 `unknown_policy`에 따릅니다.

### 3.4 Scoring Engine

- 입력과 데이터가 같으면 결과가 같은 결정론적 함수
- 점수 구성 요소별 원천과 설명 반환
- 사용 가능한 가중치만으로 적합도 재정규화
- 전체 가중치 중 확인 가능한 비중으로 confidence 계산

### 3.5 Listing Link Resolver

- `listing_sources.json`을 읽어 원천 capability 확인
- 허용된 host만 사용자 URL로 분류
- 당근은 공개 지역 지도 URL 생성
- 기타 원천은 공식 홈과 site-limited discovery link 생성
- 페이지 내용을 fetch하거나 광고 정보를 복제하지 않음

### 3.6 Home Finder Store

개인용 기본 저장소는 atomic JSON입니다.

```text
임시 파일에 직렬화
→ fsync 가능한 파일 시스템 기록
→ os.replace로 원자적 교체
```

저장 대상:

- 프로필
- 저장 검색
- 추천 실행 요약
- 이전·현재 후보 차이

API key, 로그인 쿠키, 제3자 연락처는 저장하지 않습니다.

## 4. 데이터 흐름

### 4.1 신규 추천

```text
1. validate_search_profile
2. resolve_location (필요 시)
3. create_search_profile
4. recommend_complexes
5. explain_complex_match
6. find_listing_links
7. 사용자에게 근거·주의사항과 함께 출력
```

### 4.2 저장 검색 갱신

```text
1. save_search
2. 현재 프로필로 recommend_complexes
3. 실행 결과 fingerprint 저장
4. 이전 실행과 diff
5. candidate_added / candidate_removed / rank_changed
6. reference_price_changed / transaction_count_changed
```

## 5. 배포 모드

### Personal Local

```text
stdio MCP
공공 API 온디맨드 호출
JSON profile/watchlist
```

### Team Internal

```text
Streamable HTTP
공유 API cache
PostgreSQL
내부 OAuth 또는 reverse proxy 인증
```

### Public Service

```text
TLS MCP endpoint
OAuth / tenant isolation
PostgreSQL RLS
Redis cache
rate limiting
source policy registry
audit log
```

## 6. 신뢰 경계

| 경계 | 신뢰 수준 | 처리 |
|---|---|---|
| 사용자 입력 | 비신뢰 | schema validation |
| 공공 API XML/JSON | 외부 비신뢰 | timeout, status validation, `defusedxml` |
| 저장 프로필 | 사용자 범위 | 경로 제한, atomic write |
| 제3자 URL | 외부 비신뢰 | allowlisted host classification only |
| 공식 제휴 피드 | 계약 범위 | source policy + field allowlist |
| AI 해석 | 비결정론 | deterministic facts/metrics와 분리 |

## 7. 확장 포인트

### Optional Enrichment Adapter

다음 정보는 별도 adapter 인터페이스로 추가합니다.

```text
commute_minutes
school_distance_m
school_quality_index
parking_per_household
household_count
management_fee
listing_count
asking_price_median
```

각 필드는 반드시 `source`, `observed_at`, `confidence`를 포함해야 합니다.

### Authorized Listing Adapter

공식 API 또는 계약이 확보된 원천만 다음 인터페이스를 구현합니다.

```text
search_listings
get_listing
get_listing_changes
reconcile_removed_listing
```

해당 adapter가 없을 때 MCP 도구는 링크만 반환하며, 매물 수를 `0`으로 위장하지 않고 `null`로 둡니다.
