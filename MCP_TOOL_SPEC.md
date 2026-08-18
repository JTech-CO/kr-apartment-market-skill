# KR Apartment Market MCP 도구 명세

| 항목 | 값 |
|---|---|
| 문서 버전 | 1.0.0 |
| 기준일 | 2026-08-18 |
| MCP 프로토콜 | 2026-07-28 |
| 전송 | Streamable HTTP |
| 엔드포인트 예시 | `https://api.example.com/mcp` |
| 입력·출력 스키마 | JSON Schema 2020-12 |
| 기본 시간대 | `Asia/Seoul` |
| 기계 판독 명세 | `mcp/tool-definitions.json` |

---

## 1. 목적

이 문서는 KR Apartment Market SKILL이 호출하는 MCP 서버의 공개 계약을 정의합니다. 구현 언어와 프레임워크에 관계없이 도구명, 입력, 출력, 인증, 안전성 annotation, 오류 처리, 최신성 표현을 동일하게 유지하는 것이 목적입니다.

MCP 서버는 다음 책임을 가집니다.

- 지역·단지·면적 타입의 결정론적 해석
- 최신 공개 실거래의 조회
- 취소·정정 상태 반영
- 버전 고정 산식 계산
- 출처·표본·신선도·경고 반환
- 사용자 관심 목록의 인증된 저장·조회
- 아파트Me 등 외부 원문으로 이동할 검증된 링크 생성

LLM은 도구가 반환한 값을 설명할 수 있지만, 가격·거래량·회복률을 임의로 보완하거나 재계산해서는 안 됩니다.

---

## 2. 프로토콜 계약

### 2.1 전송

- 서버는 단일 HTTPS 엔드포인트에서 `POST`를 지원합니다.
- 클라이언트는 `Accept: application/json, text/event-stream`을 보냅니다.
- 모든 요청은 `MCP-Protocol-Version: 2026-07-28` 헤더를 포함합니다.
- 요청 본문의 `_meta.io.modelcontextprotocol/protocolVersion`도 같은 값을 가져야 합니다.
- 프로토콜 세션 ID에 의존하지 않습니다.
- `GET` 또는 `DELETE`로 MCP 세션을 열거나 종료하지 않습니다.
- 장기 작업이 필요하면 요청 범위 SSE 또는 명시적 작업 핸들을 사용합니다.

### 2.2 서버 발견

서버는 최신 규격에 맞추어 `server/discover`를 구현하고 다음을 광고해야 합니다.

- 지원 프로토콜 버전
- 서버 이름과 버전
- `tools` capability
- `tools.listChanged` 지원 여부
- 인증 관련 메타데이터

### 2.3 도구 결과

성공 결과는 다음을 함께 반환합니다.

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "사용자에게 바로 설명할 수 있는 짧은 요약"
    }
  ],
  "structuredContent": {
    "...": "outputSchema와 일치하는 JSON"
  },
  "isError": false
}
```

- `structuredContent`는 반드시 도구의 `outputSchema`를 만족해야 합니다.
- 호환성을 위해 핵심 결과를 짧은 텍스트로도 반환합니다.
- 모델에 불필요한 내부 trace ID, SQL, 토큰, 원천 API 키를 반환하지 않습니다.
- 통화는 원 단위 정수, 면적은 ㎡ 단위 숫자로 반환합니다.

### 2.4 도구 실행 오류

입력 범위, 비즈니스 규칙, 원천 장애처럼 모델이 설명하거나 수정할 수 있는 오류는 `isError: true`인 도구 결과로 반환합니다.

```json
{
  "resultType": "complete",
  "content": [
    {
      "type": "text",
      "text": "동일 이름의 단지가 여러 지역에 있습니다. 지역을 지정해 주세요."
    }
  ],
  "isError": true
}
```

알 수 없는 도구, 잘못된 JSON-RPC, 스키마 자체 위반은 JSON-RPC protocol error로 반환합니다.

---

## 3. 인증과 권한

### 3.1 공개 읽기

다음 도구는 공개 데이터만 반환하므로 `noauth`를 지원할 수 있습니다.

- `kr_apartment.resolve_location`
- `kr_apartment.search_complexes`
- `kr_apartment.get_complex_snapshot`
- `kr_apartment.get_transactions`
- `kr_apartment.compare_complexes`
- `kr_apartment.get_region_pulse`
- `kr_apartment.rank_complexes`
- `kr_apartment.get_signal_feed`
- `kr_apartment.get_data_freshness`
- `kr_apartment.get_source_link`

운영자는 남용 방지를 위해 익명 호출량을 제한할 수 있습니다.

### 3.2 사용자별 데이터

다음 도구는 OAuth 2.1을 요구합니다.

| 도구 | Scope |
|---|---|
| `kr_apartment.get_watchlist` | `watchlist.read` |
| `kr_apartment.get_watchlist_brief` | `watchlist.read` |
| `kr_apartment.upsert_watchlist_item` | `watchlist.write` |
| `kr_apartment.delete_watchlist_item` | `watchlist.write` |

서버는 매 요청에서 토큰의 발급자, audience, 만료, scope를 검증합니다. 인증 실패는 HTTP 401과 적절한 `WWW-Authenticate` challenge를 반환합니다.

### 3.3 원천 권한

사용자 인증과 데이터 원천 이용권한은 별개입니다.

- 사용자가 로그인했다고 해서 미승인 민간 데이터를 읽을 수 있는 것은 아닙니다.
- 서버는 원천 레지스트리의 `access_mode`와 계약 버전을 검사합니다.
- `LINK_OUT_ONLY` 원천은 URL 외의 콘텐츠를 반환하지 않습니다.

---

## 4. 안전성 Annotation 원칙

모든 도구는 최소 다음 필드를 명시합니다.

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": false
}
```

### 4.1 해석

- `readOnlyHint=true`: 외부 상태를 바꾸지 않고 조회·계산만 수행합니다.
- `destructiveHint=true`: 사용자 데이터를 삭제하거나 되돌리기 어려운 변경을 수행합니다.
- `openWorldHint=true`: 공개 인터넷 상태를 변경하거나 외부 수신자에게 전송합니다.
- `idempotentHint=true`: 같은 인자로 재호출해도 추가 부작용이 없습니다.

### 4.2 도구별 Annotation

| 도구 | Read-only | Destructive | Open world | Idempotent | 근거 |
|---|---:|---:|---:|---:|---|
| resolve/search/read 도구 | true | false | false | true | 조회·계산만 수행 |
| get_watchlist | true | false | false | true | 사용자 데이터 조회 |
| get_watchlist_brief | true | false | false | true | 조회만 수행, 체크포인트 자동 갱신 금지 |
| upsert_watchlist_item | false | false | false | true | 사용자 계정 내부 항목 추가·수정 |
| delete_watchlist_item | false | true | false | true | 사용자 저장 항목 삭제 |

`get_watchlist_brief`는 읽기 도구입니다. 브리핑 조회와 동시에 “읽음” 체크포인트를 변경하지 않습니다. 체크포인트 갱신이 필요하면 별도 쓰기 도구로 분리해야 합니다.

---

## 5. 공통 데이터 형식

### 5.1 식별자

| 필드 | 형식 | 설명 |
|---|---|---|
| `complex_id` | UUID 문자열 | 내부 안정 단지 ID |
| `area_type_id` | UUID 문자열 | 단지 내 전용면적·타입 ID |
| `transaction_id` | UUID 문자열 | 정규화 거래 ID |
| `watchlist_id` | UUID 문자열 | 사용자 관심 목록 ID |
| `watchlist_item_id` | UUID 문자열 | 관심 항목 ID |
| `region_code` | 5~10자리 숫자 문자열 | 법정동 또는 집계용 지역 코드 |

숫자 코드의 선행 0 보존을 위해 지역 코드는 문자열로 취급합니다.

### 5.2 날짜와 시각

- 날짜: `YYYY-MM-DD`
- 시각: RFC 3339 `date-time`
- 기본 표시 시간대: Asia/Seoul
- 저장·전송은 offset을 포함합니다.

### 5.3 통화

- `price_krw`, `deposit_krw`, `monthly_rent_krw`: 원 단위 정수
- 데이터 없음: `null`
- 가격 0원과 데이터 없음은 구분합니다.

### 5.4 면적

- `exclusive_area_m2`: 전용면적 ㎡
- `supply_area_m2`: 공급면적 ㎡, 원천이 있을 때만
- `area_label`: 사용자 표시용 문자열
- `area_match_mode`: `EXACT_TYPE`, `RANGE`, `ALL_TYPES`

### 5.5 공통 신선도 객체

```json
{
  "answered_at": "2026-08-18T21:30:00+09:00",
  "metric_as_of": "2026-08-18T05:30:00+09:00",
  "latest_source_update_at": "2026-08-18T05:10:00+09:00",
  "latest_contract_date": "2026-08-17",
  "freshness_status": "CURRENT",
  "current_period_incomplete": true
}
```

### 5.6 공통 경고 객체

```json
{
  "code": "LOW_SAMPLE_SIZE",
  "severity": "warning",
  "message": "최근 90일 유효 매매가 2건뿐입니다.",
  "field": "sale_median_90d_krw"
}
```

`severity` 값:

- `info`
- `warning`
- `critical`

### 5.7 공통 출처 객체

```json
{
  "source_code": "molit_apt_sale",
  "source_name": "국토교통부 아파트 매매 실거래가 자료",
  "source_type": "PUBLIC_OPEN",
  "url": "https://www.data.go.kr/data/15126469/openapi.do",
  "retrieved_at": "2026-08-18T05:22:00+09:00",
  "usage_note": "공공데이터 원천. 계약일 기준 신고 자료."
}
```

`url`은 사용자가 열 수 있는 절대 URL이어야 합니다.

---

## 6. 공통 필터 규칙

### 6.1 거래 상태

```json
{
  "include_canceled": false,
  "revision_mode": "LATEST_ONLY"
}
```

- 기본적으로 취소 거래를 제외합니다.
- `LATEST_ONLY`는 정정된 거래의 최신 버전만 반환합니다.

### 6.2 면적 필터

세 가지 방식 중 하나만 사용합니다.

```json
{ "area_type_id": "uuid" }
```

```json
{ "area_min_m2": 83.0, "area_max_m2": 85.9 }
```

```json
{ "all_area_types": true }
```

동시에 여러 방식을 보내면 `INVALID_AREA_FILTER` 오류입니다.

### 6.3 페이지네이션

```json
{
  "limit": 50,
  "cursor": "opaque-cursor"
}
```

- 기본 `limit`: 50
- 최대 `limit`: 100
- cursor는 불투명 문자열이며 해석하지 않습니다.
- 정렬 조건이 달라지면 기존 cursor를 재사용할 수 없습니다.

### 6.4 정렬 안정성

상세 거래 기본 정렬:

```text
contract_date DESC
price_krw DESC NULLS LAST
transaction_id ASC
```

순위 기본 정렬:

```text
metric_value DESC/ASC
sample_size DESC
latest_transaction_date DESC
complex_name ASC
complex_id ASC
```

---

# 7. 도구 목록

## 7.1 `kr_apartment.resolve_location`

### 목적

자연어 지역명 또는 단지명을 안정적인 지역·단지 후보로 변환합니다. 동일 이름의 단지가 여러 곳에 있을 때 임의 선택하지 않고 후보를 반환합니다.

### 사용 시점

- 단지명·지역명이 처음 등장했을 때
- 사용자가 내부 ID를 제공하지 않았을 때
- 이전 도구 결과의 ID가 현재 대화에 없는 경우

### 사용하지 않는 경우

- 이미 검증된 `complex_id` 또는 `region_code`가 있는 경우
- 일반 주소 지오코딩만 필요한 경우

### 인증

`noauth`

### Annotation

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "openWorldHint": false,
  "idempotentHint": true
}
```

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `query` | O | 사용자가 입력한 지역·단지 문자열 |
| `entity_types` | X | `REGION`, `COMPLEX` 제한 |
| `region_hint` | X | 시도·시군구 등의 추가 힌트 |
| `limit` | X | 최대 후보 수, 1~10 |

### 주요 출력

- `normalized_query`
- `needs_disambiguation`
- `candidates[]`
  - `entity_type`
  - `entity_id`
  - `display_name`
  - `region_path`
  - `match_score`
  - `match_reason`
  - `area_types[]` — 단지인 경우 선택적
- `warnings[]`

### 서버 규칙

- 상위 후보 점수 차가 임계값보다 작으면 `needs_disambiguation=true`입니다.
- 후보가 0개여도 오류가 아니라 빈 결과를 반환할 수 있습니다.
- 지역 힌트가 단지 주소와 충돌하면 후보를 제거하거나 경고합니다.

### 예시 입력

```json
{
  "query": "성복역 롯데캐슬 골드타운",
  "entity_types": ["COMPLEX"],
  "region_hint": "용인 수지구",
  "limit": 5
}
```

---

## 7.2 `kr_apartment.search_complexes`

### 목적

지역·면적·준공연도·세대수 조건으로 단지를 탐색합니다. 특정 단지명 해석이 아니라 후보군 탐색에 사용합니다.

### 인증

`noauth`

### Annotation

읽기 전용, 비파괴, 비공개 변경 없음, 멱등.

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `query` | X | 단지명 키워드 |
| `region_code` | X | 검색 범위 |
| `min_households` | X | 최소 세대수 |
| `max_households` | X | 최대 세대수 |
| `build_year_from` | X | 최소 준공연도 |
| `build_year_to` | X | 최대 준공연도 |
| `area_min_m2` | X | 보유 면적 타입 최소값 |
| `area_max_m2` | X | 보유 면적 타입 최대값 |
| `sort` | X | `RELEVANCE`, `HOUSEHOLDS_DESC`, `BUILD_YEAR_DESC`, `NAME_ASC` |
| `limit`, `cursor` | X | 페이지네이션 |

### 주요 출력

- `complexes[]`
- `next_cursor`
- `applied_filters`
- `freshness`
- `sources[]`

### 제한

아무 조건도 없는 전국 전체 검색은 허용하지 않습니다. 최소한 `query` 또는 `region_code`가 필요합니다.

---

## 7.3 `kr_apartment.get_complex_snapshot`

### 목적

단지·면적의 최근 거래, 가격, 거래량, 최고가, 회복률, 전세가율, 추정 갭을 한 번에 반환합니다.

### 사용 시점

- “최근 실거래”, “현재 흐름”, “전고점 대비”, “전세가율” 질문
- 단일 단지 요약

### 인증

`noauth`

### 주요 입력

| 필드 | 필수 | 기본값 | 설명 |
|---|---:|---:|---|
| `complex_id` | O | - | 단지 ID |
| `area_type_id` | 조건부 | - | 정확한 면적 타입 |
| `area_min_m2`, `area_max_m2` | 조건부 | - | 명시 범위 |
| `window_days` | X | 90 | 30, 90, 180, 365 |
| `brokerage_filter` | X | `ALL` | `ALL`, `BROKERED_ONLY`, `DIRECT_ONLY` |
| `include_representative_transactions` | X | true | 대표 거래 포함 |

`area_type_id` 또는 면적 범위가 필요합니다. 단지에 면적 타입이 하나뿐인 경우 서버가 자동 선택할 수 있습니다.

### 주요 출력

```text
complex
area_scope
latest_sale
latest_lease
metrics
representative_transactions
quality
freshness
warnings
sources
```

### 핵심 `metrics`

- `sale_count_30d`
- `sale_count_90d`
- `sale_median_window_krw`
- `historical_peak_krw`
- `recovery_rate_pct`
- `latest_recovery_rate_pct`
- `jeonse_count_window`
- `jeonse_median_window_krw`
- `jeonse_ratio_pct`
- `estimated_gap_krw`
- `volume_momentum_ratio`
- `volume_momentum_state`
- `new_high_count_30d`
- `formula_version`

### 서버 규칙

- 매매 또는 전세 표본이 없으면 관련 지표는 `null`입니다.
- 추정 갭은 동·층·향이 동일한 짝이 아님을 경고합니다.
- 역대 최고가는 동일 면적 그룹의 유효 신고 거래만 사용합니다.
- 계산에 사용한 면적 범위를 그대로 반환합니다.

---

## 7.4 `kr_apartment.get_transactions`

### 목적

특정 단지 또는 지역의 개별 실거래 레코드를 상세 조회합니다.

### 인증

`noauth`

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `complex_id` 또는 `region_code` | O | 둘 중 하나 |
| `trade_types` | O | `SALE`, `JEONSE`, `MONTHLY_RENT` |
| `date_from` | O | 계약일 시작 |
| `date_to` | O | 계약일 종료 |
| 면적 필터 | X | 정확 타입 또는 범위 |
| `include_canceled` | X | 기본 false |
| `brokerage_filter` | X | 거래 방식 |
| `sort` | X | 최신순·가격순 |
| `limit`, `cursor` | X | 페이지네이션 |

### 주요 출력

- `transactions[]`
  - `transaction_id`
  - `trade_type`
  - `contract_date`
  - `price_krw` 또는 `deposit_krw`, `monthly_rent_krw`
  - `exclusive_area_m2`
  - `floor`
  - `dealing_type`
  - `is_canceled`
  - `cancellation_date`
  - `registration_date`
  - `complex`
  - `source_code`
- `next_cursor`
- `freshness`
- `warnings`
- `sources`

### 제한

- 상세 조회 기본 최대 기간은 24개월입니다.
- 지역 단위 상세 조회는 최대 6개월 또는 서버 설정 한도를 적용할 수 있습니다.
- 장기 이력은 집계 또는 내보내기 전용 기능으로 분리합니다.

---

## 7.5 `kr_apartment.compare_complexes`

### 목적

2~5개 단지를 동일 기간·동일 면적 조건으로 비교합니다.

### 인증

`noauth`

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `complex_ids` | O | 2~5개 |
| `area_type_ids` | 조건부 | 단지별 정확 면적 타입 매핑 |
| `area_min_m2`, `area_max_m2` | 조건부 | 공통 범위 |
| `window_days` | X | 기본 90 |
| `metrics` | X | 비교할 지표 목록 |
| `brokerage_filter` | X | 기본 ALL |

### 주요 출력

- `comparison_basis`
- `rows[]` — 단지별 지표
- `metric_leaders` — 지표별 상위 단지, 충분한 표본이 있을 때만
- `non_comparable_fields[]`
- `warnings[]`
- `freshness`
- `sources[]`

### 서버 규칙

- 각 단지의 면적 범위가 실제로 겹치는지 검증합니다.
- 단지별로 다른 기간을 적용하지 않습니다.
- 표본 부족 단지를 총점에서 제외합니다.
- “종합 1위”는 V1에서 제공하지 않습니다.

---

## 7.6 `kr_apartment.get_region_pulse`

### 목적

특정 지역의 거래량, 거래 단지 수, 신고가, 가격 중위값, 이전 기간 대비 변화를 요약합니다.

### 인증

`noauth`

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `region_code` | O | 지역 코드 |
| `period` | O | 시작일·종료일 또는 `LAST_30_DAYS` 등 |
| `comparison_mode` | X | `PREVIOUS_EQUAL_WINDOW`, `PREVIOUS_MONTH`, `YOY` |
| 면적 범위 | X | ㎡ |
| `min_households` | X | 단지 규모 필터 |
| `build_year_from`, `build_year_to` | X | 준공연도 필터 |
| `min_sample_size` | X | 기본 3 |
| `top_n` | X | 기본 10, 최대 30 |

### 주요 출력

- `region`
- `period`
- `comparison_period`
- `summary_metrics`
- `top_recovery_complexes`
- `top_volume_growth_complexes`
- `top_new_high_complexes`
- `coverage`
- `freshness`
- `warnings`
- `sources`

### 현재 기간 처리

현재 월이 포함되면 기본 비교는 동일 경과일 기준으로 맞춥니다. 완결 월과 현재 월 전체를 그대로 비교하지 않습니다.

---

## 7.7 `kr_apartment.rank_complexes`

### 목적

지역 내 단지를 하나의 명시적 지표로 순위화합니다.

### 인증

`noauth`

### 주요 입력

- `region_code`
- `metric`
- `period`
- 면적 범위
- 최소 세대수
- 준공연도 범위
- `min_sample_size`
- `direction`: `ASC`, `DESC`, 또는 지표 기본값
- `limit`, `cursor`

### 지원 `metric`

```text
TRANSACTION_VOLUME
VOLUME_MOMENTUM
RECOVERY_RATE
NEW_HIGH_COUNT
SALE_MEDIAN
JEONSE_RATIO
ESTIMATED_GAP
PRICE_CHANGE
```

### 주요 출력

- `metric_definition`
- `ranking[]`
  - `rank`
  - `complex`
  - `area_scope`
  - `metric_value`
  - `unit`
  - `sample_size`
  - `confidence`
  - `latest_transaction_date`
- `next_cursor`
- `excluded_count`
- `warnings`
- `freshness`

### 서버 규칙

- 표본 조건을 통과하지 못한 단지는 제외합니다.
- 추정 갭은 낮을수록 상위가 될 수 있으므로 기본 정렬 방향을 지표 정의에서 가져옵니다.
- null 값은 순위에 넣지 않습니다.

---

## 7.8 `kr_apartment.get_signal_feed`

### 목적

지역·단지에서 최근 감지된 조건 기반 시장 신호를 조회합니다.

### 인증

`noauth`

### 주요 입력

- `region_code` 또는 `complex_ids`
- `signal_codes[]`
- `detected_from`, `detected_to`
- 면적 범위
- `min_confidence`
- `limit`, `cursor`

### 지원 신호

```text
NEW_HIGH
TRADING_RESUMED
VOLUME_ACCELERATION
RECOVERY_THRESHOLD_CROSSED
JEONSE_RATIO_RISING
ESTIMATED_GAP_NARROWING
SHORT_TERM_TREND_CANDIDATE
```

### 주요 출력

- `signals[]`
  - `signal_id`
  - `signal_code`
  - `detected_at`
  - `complex`
  - `area_scope`
  - `strength`
  - `confidence`
  - `formula_version`
  - `evidence`
  - `expires_at`
- `next_cursor`
- `freshness`
- `warnings`

### 해석 제한

신호는 조건 충족 이벤트이며 가격 상승·하락 예측이 아닙니다. 서버의 텍스트 요약에도 이를 명시합니다.

---

## 7.9 `kr_apartment.get_data_freshness`

### 목적

데이터셋별 마지막 성공 수집, 원천 갱신, 지연 여부를 확인합니다.

### 인증

`noauth`

### 주요 입력

- `dataset_codes[]` — 선택적
- `region_code` — 특정 지역 파티션 상태가 필요할 때

### 주요 출력

- `datasets[]`
  - `dataset_code`
  - `status`
  - `last_successful_collection_at`
  - `source_watermark_at`
  - `latest_contract_date`
  - `next_scheduled_collection_at`
  - `delay_minutes`
  - `coverage_note`
- `answered_at`

### 사용 규칙

SKILL은 원천 지연이 의심되거나 사용자가 “업데이트 시각”을 묻는 경우 이 도구를 호출합니다. 모든 단지 스냅샷 앞에 별도 호출할 필요는 없으며, 각 도구가 이미 신선도 객체를 반환합니다.

---

## 7.10 `kr_apartment.get_source_link`

### 목적

공공 원문 또는 아파트Me 링크 전용 원천의 검증된 사용자 이동 URL을 생성합니다.

### 인증

`noauth`

### 주요 입력

| 필드 | 필수 | 설명 |
|---|---:|---|
| `source_code` | O | `molit_rt`, `data_go_kr`, `apt2me` 등 |
| `entity_type` | O | `COMPLEX`, `REGION`, `DATASET`, `RANKING` |
| `complex_id` | 조건부 | 단지 링크 |
| `region_code` | 조건부 | 지역 링크 |
| `dataset_code` | 조건부 | 데이터셋 링크 |
| `view` | X | 원천이 지원하는 페이지 유형 |

### 주요 출력

- `links[]`
  - `title`
  - `url`
  - `source_code`
  - `access_mode`
  - `content_ingested`
  - `last_verified_at`
- `warnings[]`

### 서버 규칙

- allowlist 도메인만 반환합니다.
- `apt2me`가 `LINK_OUT_ONLY`이면 `content_ingested=false`여야 합니다.
- 매핑이 불확실하면 아파트Me 검색 또는 지역 통계 상위 페이지 링크만 반환합니다.
- URL을 만들 수 없다고 해서 추측한 path를 반환하지 않습니다.

---

## 7.11 `kr_apartment.get_watchlist`

### 목적

인증된 사용자의 관심 목록과 항목을 조회합니다.

### 인증

OAuth `watchlist.read`

### Annotation

읽기 전용, 비파괴, open world 아님, 멱등.

### 주요 입력

- `watchlist_id` — 생략 시 기본 목록
- `include_inactive` — 기본 false
- `limit`, `cursor`

### 주요 출력

- `watchlist`
- `items[]`
  - `watchlist_item_id`
  - `entity_type`
  - `complex` 또는 `region`
  - `area_scope`
  - `trade_types`
  - `signal_rules`
  - `created_at`
  - `updated_at`
- `next_cursor`

사용자 OAuth subject, 이메일, 내부 권한 정보를 결과에 반환하지 않습니다.

---

## 7.12 `kr_apartment.upsert_watchlist_item`

### 목적

인증된 사용자의 관심 단지·지역 조건을 추가하거나 동일 키의 항목을 갱신합니다.

### 인증

OAuth `watchlist.write`

### Annotation

```json
{
  "readOnlyHint": false,
  "destructiveHint": false,
  "openWorldHint": false,
  "idempotentHint": true
}
```

### 주요 입력

- `watchlist_id` — 생략 시 기본 목록
- `entity_type`
- `complex_id` 또는 `region_code`
- 면적 범위 또는 `area_type_id`
- `trade_types[]`
- `signal_rules[]`
- `label` — 선택적 사용자 표시명
- `client_request_id` — 재시도 멱등 키, 선택적

### 주요 출력

- `operation`: `CREATED` 또는 `UPDATED`
- `item`
- `warnings[]`

### 서버 규칙

- 사용자별 동일 엔티티·동일 조건 natural key로 업서트합니다.
- 서버는 요청 사용자가 해당 watchlist의 소유자인지 검증합니다.
- 민간 원천 구독을 자동 활성화하지 않습니다.
- 쓰기 성공 후 저장된 조건을 그대로 반환합니다.

---

## 7.13 `kr_apartment.delete_watchlist_item`

### 목적

인증된 사용자의 관심 항목을 삭제합니다.

### 인증

OAuth `watchlist.write`

### Annotation

```json
{
  "readOnlyHint": false,
  "destructiveHint": true,
  "openWorldHint": false,
  "idempotentHint": true
}
```

### 주요 입력

- `watchlist_item_id`
- `client_request_id` — 선택적 멱등 키

### 주요 출력

- `deleted`
- `watchlist_item_id`
- `deleted_at`

### 서버 규칙

- 존재하지 않거나 이미 삭제된 항목에 대한 재호출은 `deleted=true`와 상태 설명을 반환해 멱등하게 처리할 수 있습니다.
- 다른 사용자의 항목 여부를 추측할 수 없도록 `NOT_FOUND_OR_FORBIDDEN`으로 통합할 수 있습니다.

---

## 7.14 `kr_apartment.get_watchlist_brief`

### 목적

관심 항목의 지정 시점 이후 신규·정정·취소 거래와 신호 변화를 읽기 전용으로 요약합니다.

### 인증

OAuth `watchlist.read`

### 주요 입력

- `watchlist_id` — 생략 시 기본 목록
- `since` — 필수 또는 최근 24시간 기본값
- `until` — 기본 현재 시각
- `change_types[]`
  - `NEW_TRANSACTION`
  - `CORRECTED_TRANSACTION`
  - `CANCELED_TRANSACTION`
  - `NEW_HIGH`
  - `SIGNAL_STARTED`
  - `SIGNAL_ENDED`
- `max_events_per_item` — 기본 20

### 주요 출력

- `period`
- `items[]`
  - 관심 항목
  - `changes[]`
  - `summary`
- `total_change_count`
- `freshness`
- `warnings`

### 서버 규칙

- 조회로 읽음 상태나 체크포인트를 변경하지 않습니다.
- 변경이 없으면 정상적으로 빈 `changes` 배열을 반환합니다.
- 동일 이벤트는 안정적 `event_id`로 중복 제거합니다.

---

# 8. 오류 코드

## 8.1 입력·해석 오류

| 코드 | 의미 | 모델의 회복 행동 |
|---|---|---|
| `AMBIGUOUS_LOCATION` | 후보가 여러 개 | 후보를 사용자에게 제시 |
| `ENTITY_NOT_FOUND` | 지역·단지 없음 | 철자·지역 힌트 요청 |
| `INVALID_AREA_FILTER` | 면적 필터 충돌 | 한 방식만 선택해 재호출 |
| `AREA_TYPE_NOT_FOUND` | 단지에 해당 면적 없음 | 사용 가능한 면적 제시 |
| `INVALID_DATE_RANGE` | 날짜 역전·범위 초과 | 범위 수정 |
| `QUERY_TOO_BROAD` | 전국 상세 등 과도한 범위 | 지역·기간 축소 |
| `INVALID_CURSOR` | cursor 만료·정렬 불일치 | 첫 페이지부터 재호출 |

## 8.2 데이터 오류

| 코드 | 의미 | 행동 |
|---|---|---|
| `SOURCE_DELAYED` | SLA 초과 | 마지막 정상 시각과 경고 표시 |
| `SOURCE_UNAVAILABLE` | 원천 장애 | 캐시 여부 설명, 추측 금지 |
| `INSUFFICIENT_DATA` | 계산 표본 부족 | null 지표와 표본 수 표시 |
| `PARTNER_SOURCE_NOT_AUTHORIZED` | 미승인 민간 원천 | 공공 데이터 또는 link-out 사용 |
| `MAPPING_CONFIDENCE_LOW` | 단지 매칭 불확실 | 후보 확인 요청 |

## 8.3 인증·권한 오류

| 코드 | 의미 |
|---|---|
| `UNAUTHENTICATED` | 로그인 또는 토큰 필요 |
| `INSUFFICIENT_SCOPE` | 필요한 OAuth scope 없음 |
| `NOT_FOUND_OR_FORBIDDEN` | 리소스 없음 또는 접근 불가 |

## 8.4 쓰기 오류

| 코드 | 의미 |
|---|---|
| `WATCHLIST_LIMIT_REACHED` | 사용자 항목 한도 초과 |
| `CONFLICT` | 동시 수정 충돌 |
| `IDEMPOTENCY_KEY_REUSED` | 다른 payload로 같은 키 재사용 |

## 8.5 운영 오류

| 코드 | 의미 |
|---|---|
| `RATE_LIMITED` | 호출 한도 초과 |
| `TIMEOUT` | 처리 시간 초과 |
| `INTERNAL_ERROR` | 내부 오류, 상세 진단 미노출 |

---

## 9. 재시도 정책

| 오류 | 자동 재시도 | 기본 정책 |
|---|---:|---|
| 429 / `RATE_LIMITED` | 가능 | `Retry-After`, 최대 2회 |
| 5xx / `SOURCE_UNAVAILABLE` | 가능 | 지수 백오프, 최대 2회 |
| `TIMEOUT` | 조건부 | 범위 축소 후 1회 |
| `AMBIGUOUS_LOCATION` | 금지 | 사용자 선택 필요 |
| `INVALID_*` | 금지 | 인자 수정 후 새 호출 |
| 인증 오류 | 금지 | OAuth 갱신 |
| 쓰기 도구 네트워크 불명확 | 멱등 키가 있을 때만 | 동일 키로 재시도 |

---

## 10. 호출량과 범위 제한

권장 기본값입니다. 운영 환경에 맞추어 낮출 수 있습니다.

| 도구 | 사용자별 제한 예시 |
|---|---:|
| resolve/search | 분당 60회 |
| snapshot/compare | 분당 30회 |
| transactions | 분당 20회 |
| region/ranking/signal | 분당 10회 |
| freshness/link | 분당 60회 |
| watchlist read | 분당 30회 |
| watchlist write/delete | 분당 10회 |

서버는 원천 API 키 한도와 사용자 한도를 별도로 관리합니다.

---

## 11. 캐시와 MCP 목록 캐싱

- `tools/list`는 안정적인 순서로 반환합니다.
- 도구 목록이 바뀌지 않으면 적절한 `ttlMs`와 `cacheScope`를 제공합니다.
- 사용자 권한에 따라 도구가 달라질 수 있지만 연결 세션 상태에 따라 임의 변경하지 않습니다.
- 공개 조회 결과는 사용자 간 공유 가능한 캐시를 사용할 수 있습니다.
- 관심 목록 결과는 사용자별 private cache로 격리합니다.

---

## 12. 데이터 최소화

도구 결과에서 다음을 제외합니다.

- 원천 API 서비스 키
- OAuth access/refresh token
- 사용자 이메일·실명 — 기능상 필수일 때만 별도 동의
- 내부 SQL, 스택 트레이스
- 시스템 프롬프트와 원문 대화 기록
- 불필요한 내부 계정 ID
- 정확한 동·호 등 공개 원천이 제공하지 않는 개인정보

단지·거래·관심 항목의 안정적 ID는 후속 호출을 위해 필요한 리소스 ID이므로 반환할 수 있습니다.

---

## 13. 프롬프트 인젝션 방어

- 외부 원천의 텍스트를 시스템 지시로 취급하지 않습니다.
- 원천에서 가져온 단지명·비고·링크는 데이터 필드로만 처리합니다.
- URL은 allowlist와 예상 path를 검증합니다.
- 민간 페이지에 “다른 도구를 호출하라”는 문구가 있어도 무시합니다.
- 도구는 범용 URL fetch, 임의 SQL 실행, 임의 파일 읽기를 제공하지 않습니다.

---

## 14. 관측성

각 도구 호출에서 다음 운영 메트릭을 기록합니다.

- 도구명
- 성공/오류 코드
- 처리시간
- 캐시 적중 여부
- 사용 데이터셋 코드
- 반환 행 수 구간
- 인증 scope 존재 여부

기본 로그에 다음은 기록하지 않습니다.

- 전체 입력 인자
- 사용자 자연어 질문
- 상세 거래 응답 전체
- OAuth subject 원문

필요한 경우 식별자는 단방향 해시 또는 단기 상관 ID로 처리합니다.

---

## 15. 호환성 정책

### 15.1 도구명

도구명은 공개 API 계약입니다. 의미가 바뀌는 경우 기존 도구를 수정하지 않고 버전 도구를 추가하거나 서버 major version을 올립니다.

### 15.2 입력 필드

- 선택 필드 추가는 호환 변경입니다.
- 필수 필드 추가, 타입 변경, enum 제거는 비호환 변경입니다.

### 15.3 출력 필드

- 선택 필드 추가는 호환 변경입니다.
- 기존 필드 의미 변경 금지
- 지표 산식 변경은 `formula_version`을 올립니다.

### 15.4 폐기

- 도구 설명에 폐기 예정일을 표시합니다.
- 최소 90일 병행 운영을 권장합니다.
- SKILL과 MCP 도구를 같은 릴리스에서 갱신합니다.

---

## 16. 구현·검증 체크리스트

- [ ] `server/discover`가 지원 규격과 capabilities를 반환한다.
- [ ] `POST /mcp`가 JSON과 request-scoped SSE를 지원한다.
- [ ] 모든 요청에서 protocol version header와 `_meta`를 검증한다.
- [ ] 모든 도구가 유효한 JSON Schema 2020-12를 가진다.
- [ ] 모든 도구가 `readOnlyHint`, `destructiveHint`, `openWorldHint`를 명시한다.
- [ ] structuredContent가 outputSchema를 통과한다.
- [ ] 공개 읽기와 OAuth 쓰기 경계가 서버에서 강제된다.
- [ ] 취소 거래가 기본 집계에서 제외된다.
- [ ] 미승인 아파트Me 콘텐츠 수집 경로가 비활성화되어 있다.
- [ ] URL allowlist가 적용된다.
- [ ] 14개 도구를 정상·오류·권한 부족 입력으로 테스트한다.
- [ ] MCP Inspector에서 목록, 호출, 오류, annotation을 검증한다.
- [ ] ChatGPT 개발자 모드에서 golden prompt를 재생한다.

---

## 17. 참고

- MCP Specification 2026-07-28: https://modelcontextprotocol.io/specification/2026-07-28
- MCP Tools: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- MCP Streamable HTTP: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- OpenAI Define tools: https://developers.openai.com/plugins/plan/tools
- OpenAI Build an MCP server: https://developers.openai.com/plugins/build/mcp-server
- OpenAI Authentication: https://developers.openai.com/plugins/build/auth
- OpenAI Tool reference: https://developers.openai.com/plugins/reference

