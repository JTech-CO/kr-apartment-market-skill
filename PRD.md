# PRD — KR Apartment Market AI Skill v3.0.0

문서 상태: 구현 기준선  
제품명: KR Apartment Market AI Skill  
릴리스명: AI Home Finder & Listing Link Hub  
버전: 3.0.0  
기준일: 2026-08-26  
라이선스: MIT

## 1. 제품 요약

KR Apartment Market AI Skill v3.0.0은 사용자의 주거 선호를 명시적인 조건과 가중치로 변환하고, 국토교통부 공공 실거래 데이터를 근거로 적합도가 높은 아파트 단지를 추천하며, 네이버 부동산·당근 부동산·피터팬·아실·KB부동산 등의 현재 광고매물을 원문에서 확인하도록 연결하는 플랫폼 중립형 AI Home Finder입니다.

제품은 다음 두 결과를 한 화면 또는 한 응답에서 제공합니다.

1. **근거 기반 후보 추천**: 공식 실거래와 결정론적 점수
2. **행동 가능한 탐색 경로**: 각 광고매물 플랫폼의 원문 링크

## 2. 문제 정의

### 2.1 사용자 문제

주택 탐색자는 예산, 지역, 통근, 면적, 가족 구성, 연식, 주차, 학군 등의 조건을 동시에 고려합니다. 그러나 실거래 조회, 단지 비교, 현재 광고매물 탐색은 서로 다른 서비스와 화면에 분리되어 있습니다.

대표적인 사용자 작업:

```text
조건을 메모
→ 지역별 단지 검색
→ 실거래 확인
→ 동일 면적 거래만 다시 분류
→ 현재 매물 플랫폼별 재검색
→ 후보를 표로 비교
→ 다음 날 매물과 가격 변화를 다시 확인
```

### 2.2 시장 공백

개별 플랫폼은 실거래 또는 자사 광고매물을 제공하지만, 사용자의 복합 선호를 플랫폼 중립적으로 점수화하고 공공데이터 근거와 복수 플랫폼 원문 경로를 함께 제공하는 오픈소스 AI 워크플로는 제한적입니다.

### 2.3 기술 문제

- AI가 현재 가격을 기억으로 추측할 수 있음
- 동일 이름 단지와 행정구역의 모호성
- 다른 면적·거래 유형을 섞은 비교
- 취소 거래와 신고 지연
- 광고가격과 실거래 혼동
- 제3자 매물의 무단 수집·재배포 위험
- 통근·학군·주차 등 미연결 데이터의 환각
- 추천 점수의 설명 불가능성

## 3. 제품 비전

> 사용자가 원하는 집을 자연어로 설명하면, AI가 조건을 검증 가능한 프로필로 바꾸고, 공공 실거래로 후보를 좁히며, 추천 이유와 불확실성을 설명하고, 실제 매물은 원문 플랫폼에서 즉시 확인하도록 연결한다.

## 4. 목표

### G-01 조건 구조화

자연어 또는 JSON 입력을 필수 조건·선호 조건·제외 조건·가중치가 포함된 버전형 프로필로 변환합니다.

### G-02 설명 가능한 추천

각 후보의 점수 구성 요소, 추천 이유, 양보해야 할 조건과 미확인 항목을 반환합니다.

### G-03 공공데이터 근거

가격·면적·거래량·최근성·회복률 등 핵심 추천 근거를 공공 실거래 또는 명시된 파생 지표에서 계산합니다.

### G-04 광고매물 원문 연결

복수 플랫폼의 공식 홈·지역 지도·원문 탐색 링크를 제공합니다.

### G-05 반복 탐색

프로필과 검색을 저장하고 후보·순위·기준가격·거래건수 변화를 비교합니다.

### G-06 독립 배포

별도 `real-estate-mcp` 설치 없이 하나의 저장소와 하나의 MCP 서버로 실행합니다.

## 5. 비목표

- 제3자 플랫폼 전체 매물 크롤링
- 허가되지 않은 사진·설명·연락처 재배포
- 미래 가격 예측 또는 투자 수익 보장
- 자동 매수·계약·중개
- 대출 승인·감정평가·세무 결과 확정
- 학군 서열화 또는 교육 성과 보장
- 토지·상업용을 아파트와 동일한 추천 모델로 점수화
- 로그인 우회 또는 비공식 API 역공학

## 6. 대상 사용자

### P-01 실수요자

- 첫 주택 또는 갈아타기 후보 탐색
- 통근·가족·예산을 함께 고려
- 여러 플랫폼을 반복 검색하는 사용자

### P-02 전월세 탐색자

- 보증금·월세 상한
- 최근 임대차 거래와 전세가율 확인
- 원룸·오피스텔·빌라 확장을 원하는 사용자

### P-03 공인중개사·상담 실무자

- 고객 조건을 표준화
- 후보 단지와 공공 근거를 빠르게 제시
- 광고매물은 원문에서 확인

### P-04 프롭테크·AI 개발자

- 자체 검색 UI, 상담 AI, 지역 대시보드 구축
- MCP·API·PostgreSQL 확장
- 공식 제휴 피드 연결

### P-05 콘텐츠·리서치 사용자

- 조건별 단지 비교
- 시장 흐름과 매물 탐색 경로를 함께 정리

## 7. 핵심 사용자 시나리오

### US-01 자연어 조건 입력

```text
성남 분당구나 용인 수지구에서 9억 이하 매매 아파트를 찾고 있다.
전용 74~86㎡, 준공 20년 이내를 선호하고 최근 거래가 3건 이상이면 좋겠다.
```

시스템은 다음을 수행합니다.

1. 지역 후보를 법정동 코드로 해석
2. 매매·9억·74~86㎡를 명시적 조건으로 변환
3. “20년 이내”와 “3건 이상”의 hard/preference 여부 확인
4. 프로필 반환

### US-02 후보 추천

시스템은 각 지역의 실거래를 조회하고 단지별 facts를 만든 뒤, 필수 조건을 적용하고 점수를 계산합니다.

### US-03 추천 이유 확인

사용자는 특정 단지가 왜 1위인지, 어떤 정보가 부족한지 확인합니다.

### US-04 현재 광고매물 확인

사용자는 추천 카드에서 네이버·당근·피터팬·아실·KB 링크를 열어 현재 광고 상태를 원문에서 확인합니다.

### US-05 검색 저장

사용자는 같은 조건을 저장하고 다음 실행에서 후보·순위·가격 변화를 확인합니다.

### US-06 사용자 제공 매물 비교

사용자는 특정 플랫폼에서 찾은 URL을 붙여넣고 지원 원천 여부를 확인한 뒤 공식 실거래와 수동 비교합니다. v3 기본 구현은 URL 내용을 자동 수집하지 않습니다.

## 8. 제품 범위

### 8.1 v3.0.0 In Scope

- 아파트 매매·전세·월세 추천
- 최대 20개 법정동 코드
- 공공 실거래 기반 후보 생성
- 예산·면적·연식·거래량 hard constraints
- 11개 점수 구성 요소
- 적합도·신뢰도 분리
- 11개 링크 원천 레지스트리
- 5개 기본 링크 원천
- 사용자 제공 URL source classification
- 로컬 JSON 프로필·저장 검색
- PostgreSQL `finder`·`listing` schema
- 32개 canonical MCP 도구

### 8.2 Future Scope

- 대중교통·자동차 통근 API
- 학교·생활 인프라 공공데이터
- 공동주택 세대수·주차·관리비
- 정식 제휴 매물 API
- listing deduplication
- 브라우저 Listing Bridge
- 중개사 first-party feed
- 토지·상업용·경매 독립 추천 모델

## 9. 기능 요구사항

### FR-PROFILE-001 프로필 검증

입력 JSON을 canonical schema로 검증하고 정규화해야 합니다.

수용 기준:

- 잘못된 거래 유형 거부
- 5자리 법정동 코드만 허용
- 예산 최소값이 최대값을 넘으면 거부
- 면적 최소값이 최대값을 넘으면 거부
- 지원하지 않는 가중치 거부
- 가중치 합을 1로 정규화
- 프로필 schema version 반환

### FR-PROFILE-002 프로필 CRUD

프로필 생성·조회·수정·삭제를 지원해야 합니다.

수용 기준:

- 각 변경 시 `updated_at` 갱신
- 삭제 후 조회 불가
- patch update 후 전체 프로필 재검증
- 로컬 파일 쓰기는 atomic해야 함

### FR-CANDIDATE-001 공공데이터 후보 생성

각 지역·기간의 아파트 매매와 임대차를 조회하고 단지별 후보 facts를 생성해야 합니다.

수용 기준:

- 취소 거래 기본 제외
- 단지명 정규화
- 거래 유형별 기준 가격 분리
- 면적·최신 계약일·표본 수 포함
- source month 포함

### FR-CONSTRAINT-001 필수 조건 적용

필수 조건 위반 후보를 순위에서 제외해야 합니다.

수용 기준:

- 제외 이유 배열 반환
- 점수 감점으로만 처리하지 않음
- 미확인 조건은 profile unknown policy 적용

### FR-SCORE-001 결정론적 점수

점수 계산은 AI 모델이 아니라 코드에서 수행해야 합니다.

수용 기준:

- 동일 입력·facts·as_of에서 동일 결과
- 0~100 범위
- 구성 요소별 score·weight·source·explanation
- 적합도와 신뢰도 별도 반환
- scoring model version 기록

### FR-SCORE-002 다양성

복수 지역 검색에서는 선택적으로 지역 다양성을 유지해야 합니다.

수용 기준:

- `none`: 순수 점수 순
- `region`: 지역 round-robin 후 limit 적용

### FR-EXPLAIN-001 설명

추천 이유는 도구 결과에 근거해야 합니다.

수용 기준:

- strengths
- tradeoffs
- unknowns
- exclusion reasons
- AI가 새로운 점수를 계산하지 않음

### FR-LINK-001 원천 registry

광고매물 원천을 데이터 파일과 DB registry로 관리해야 합니다.

수용 기준:

- source code 유일
- HTTPS homepage
- allowed hosts
- access mode
- supported property types
- reviewed date

### FR-LINK-002 링크 생성

프로필 또는 후보에 대해 선택된 원천 링크를 반환해야 합니다.

수용 기준:

- 공식 homepage 항상 반환 가능
- 당근 지역 지도 URL percent encoding
- 미검증 deep link를 공식 API처럼 표현하지 않음
- source capability 포함

### FR-LINK-003 사용자 URL 검사

사용자 제공 URL을 fetch하지 않고 source를 분류해야 합니다.

수용 기준:

- HTTPS만 허용
- hostname allowlist 비교
- 지원 원천·미지원 원천 구분
- content 또는 개인정보 저장 없음

### FR-SAVED-001 저장 검색

프로필과 검색 설정을 저장해야 합니다.

수용 기준:

- label
- date range
- candidate limit
- 마지막 실행 fingerprint

### FR-SAVED-002 변경 비교

이전 추천과 현재 추천의 변화를 반환해야 합니다.

수용 기준:

- candidate added/removed
- rank changed
- reference price changed
- transaction count changed
- 최초 실행은 baseline 없음 명시

### FR-MARKET-001 v2 기능 보존

기존 17개 `kr_apartment.*` 도구의 이름과 핵심 동작을 유지해야 합니다.

### FR-COMPAT-001 호환 계층

환경 설정에 따라 내장 real-estate-mcp 호환 도구를 같은 서버에 등록해야 합니다.

수용 기준:

- canonical-only 32개
- compatibility-on 48개
- 호환 계층 실패가 canonical server를 중단시키지 않음

## 10. 데이터 요구사항

### 10.1 Search Profile

필수 필드:

```text
profile_id
schema_version
transaction_type
property_types
lawd_codes
budget
area
weights
unknown_policy
listing_sources
```

### 10.2 Candidate Facts

```text
lawd_code
region_name
complex_name
transaction_type
reference_price
sale/jeonse/monthly medians
latest_contract_date
transaction_count
area range and median
representative_build_year
recovery_rate
jeonse_ratio
estimated_gap
source_months
enrichment
```

### 10.3 Score

```text
match_score
confidence_score
excluded
exclusion_reasons
components
strengths
tradeoffs
unknowns
available_weight
total_weight
```

### 10.4 Listing Link

```text
source_id
source_name
access_mode
link_type
url
query_context
metadata_available
policy_note
```

## 11. 데이터 원천 우선순위

1. 국토교통부 실거래 공공 API
2. 청약홈·ODCloud 공공 API
3. 저장된 정규화 거래·지표 snapshot
4. 검증된 공공 enrichment
5. 공식 제휴 API·first-party feed
6. 사용자 입력
7. 제3자 원문 링크

AI 내부 지식은 현재 가격·현재 매물의 사실 원천으로 사용하지 않습니다.

## 12. 추천 점수 요구사항

### 12.1 기본 구성 요소

- affordability
- area_fit
- building_age
- liquidity
- recency
- recovery
- jeonse_safety
- commute
- education
- parking
- listing_availability

### 12.2 신뢰도

신뢰도는 최소 다음을 반영합니다.

- 이용 가능한 가중치 비율
- 거래 표본 수
- 최신 거래 경과일
- enrichment source presence

### 12.3 미확인 데이터

`null`을 0으로 바꾸지 않습니다. “정보 없음”과 “0건·0원”을 구분합니다.

## 13. 광고매물 정책 요구사항

### POL-LISTING-001

모든 신규 원천은 승인 전 `LINK_OUT_ONLY`여야 합니다.

### POL-LISTING-002

매물 사진·설명·연락처 저장은 명시적 allow flag가 없으면 차단해야 합니다.

### POL-LISTING-003

광고가격을 “현재 시세”로 표현하지 않습니다.

### POL-LISTING-004

플랫폼 링크 장애가 추천 실패를 유발해서는 안 됩니다.

### POL-LISTING-005

MIT 라이선스와 제3자 데이터 권리를 구분해 고지해야 합니다.

## 14. UX 요구사항

### 14.1 조건 확인

AI는 추천 전에 해석한 핵심 조건을 요약합니다. 단, 사용자가 이미 구조화된 JSON을 제공했고 검증이 통과하면 불필요한 재질문을 하지 않습니다.

### 14.2 추천 카드

각 카드에 다음을 포함합니다.

- 순위
- 단지명·지역
- 적합도·신뢰도
- 기준 거래 유형·면적·기간
- 최근 거래·중위값·표본 수
- 추천 이유 2~4개
- 트레이드오프
- 미확인 항목
- 원문 링크

### 14.3 가독성

- 기본 본문 16px 이상
- 적합도와 신뢰도 색상만으로 구분하지 않음
- 모바일에서 수평 스크롤 최소화
- 링크 원천명을 명시

## 15. 비기능 요구사항

### NFR-01 성능

- 최대 지역 수 20
- 기본 후보 limit 20, 최대 100
- 지역 API 병렬성 기본 4
- 외부 API timeout 기본 20초
- retry count 기본 3

### NFR-02 안정성

- 외부 원천별 오류 격리
- 부분 성공 반환
- JSON atomic write
- invalid URL과 malformed profile 예외 처리

### NFR-03 보안

- XML `defusedxml`
- API key 로그 금지
- URL fetch 금지
- hostname allowlist
- 공개 서비스 DB RLS
- OAuth subject hash

### NFR-04 관측 가능성

운영형 배포에서는 다음을 기록합니다.

- request ID
- tool name
- latency
- source calls
- result status
- scoring model version
- source watermark
- policy decision

### NFR-05 호환성

- Python 3.11·3.12
- stdio·Streamable HTTP
- JSON Schema 2020-12
- PostgreSQL 16+

## 16. 오류 계약

```text
VALIDATION_ERROR
NOT_FOUND
AMBIGUOUS_LOCATION
CONFIG_ERROR
SOURCE_TIMEOUT
SOURCE_RATE_LIMITED
SOURCE_UNAVAILABLE
PARTIAL_RESULT
UNSUPPORTED_SOURCE
POLICY_DENIED
INTERNAL_ERROR
```

오류는 사용자가 수정 가능한 항목, 재시도 가능 여부, 실패한 원천을 구분합니다.

## 17. 성공 지표

### 제품 품질

```yaml
hard_constraint_violation: 0
score_reproducibility: 100%
source_attribution_presence: 100%
asking_price_labeling: 100%
listing_policy_default_link_only: 100%
unauthorized_metadata_storage: 0
recommendation_explanation_presence: 100%
unknown_data_disclosure: 100%
```

### 기술 품질

```yaml
canonical_tool_count: 32
integrated_tool_count: 48
runtime_tests: all_pass
python_compile: all_pass
zip_crc: all_pass
package_install_smoke_test: pass
```

## 18. QA 계획

### Profile

- 빈 지역
- 잘못된 법정동 코드
- 음수 예산
- 최소·최대 역전
- 합이 0인 가중치
- 미지원 source

### Recommendation

- 예산 초과 제외
- 면적 비중첩 제외
- 거래 0건
- 취소 거래만 존재
- 같은 단지명 다른 지역
- 동일 점수 tie-break
- 지역 다양성

### Confidence

- 모든 enrichment 존재
- 모든 enrichment 없음
- 거래 1건
- 최신 거래 1년 초과

### Listing Links

- 지원 source
- 미지원 source
- 당근 한글 지역 encoding
- 사용자 URL hostname 변형
- HTTP URL 거부
- 악성 scheme 거부

### Saved Search

- 최초 실행
- 후보 추가·삭제
- 순위 상승·하락
- 가격 변화
- 손상된 JSON 복구 실패 메시지

### Regression

- 기존 17개 도구 등록
- 기존 지표 fixture
- 기존 관심 목록
- 호환 도구 16개

## 19. 마일스톤

### M0 완료 — v2 기반선

실거래·청약 런타임, 시장 지표, 관심 단지, 호환 계층.

### M1 완료 — v3 core

검색 프로필, 후보 builder, scoring, explain, listing registry.

### M2 완료 — 저장 검색

프로필 CRUD, 저장 검색, run diff.

### M3 완료 — 패키지·문서

SKILL, MCP catalog, SQL migration, 테스트, 소개 페이지, ZIP.

### M4 향후 — enrichment

통근·학군·주차·세대수 adapter.

### M5 향후 — authorized listings

공식 제휴 API와 first-party feed.

## 20. 릴리스 승인 기준

v3.0.0 소스 ZIP은 다음을 모두 만족할 때 릴리스합니다.

- 32개 canonical 도구 catalog/runtime 일치
- compatibility 포함 48개 등록
- 신규 Home Finder 테스트 포함 전체 통과
- package static validator 통과
- SQL 정적 invariant 통과
- source registry 11개와 policy 일치
- README·PRD·SKILL·MCP spec v3 표기
- THIRD_PARTY_NOTICES와 upstream MIT 고지 포함
- ZIP CRC 검사 통과
- 실제 API key 미포함
