# 시장 지표 정의

- 문서 버전: 1.0.0
- Formula set: `krams-market-v1`
- 기준일: 2026-08-18

## 1. 공통 계산 원칙

### 1.1 기본 필터

모든 V1 지표는 별도 표기가 없으면 다음 거래만 사용한다.

```text
record_status = VALID
property_type = APARTMENT
contract_date <= as_of_date
price/deposit가 거래 유형별 유효 범위
단지 매핑이 확정되었거나 허용 임계값 이상
```

취소 거래는 원본과 revision에는 남지만 기본 지표에서 제외한다. 극단값 후보는 자동 삭제하지 않으며 `quality_flags`와 포함 정책을 결과에 기록한다.

### 1.2 면적 범위

우선순위:

1. 정확한 `area_type_id`
2. 같은 단지의 전용면적 허용 오차 `±0.50㎡`
3. 사용자가 명시한 면적 범위
4. 국민평형 검색용 `82.00~86.00㎡`

서로 다른 단지 비교에서는 동일 `area_scope`를 적용한다. 공급면적 또는 마케팅 평형을 전용면적으로 간주하지 않는다.

### 1.3 기간

- 날짜 기준: `contract_date`
- 범위: 양 끝 포함
- `as_of_date`: 한국 시간대의 기준일
- 최근 30일: `as_of_date - 29일`부터 `as_of_date`
- 직전 30일: 최근 30일 시작일 이전 30일
- 최근 90일: `as_of_date - 89일`부터 `as_of_date`

현재 월 집계는 완료 월과 직접 비교하지 않고 `PARTIAL` 또는 동일 경과일 비교를 사용한다.

### 1.4 중위값

정렬된 값이 홀수이면 중앙값, 짝수이면 가운데 두 값의 산술평균이다. KRW 정수 결과는 1원 단위 반올림한다.

### 1.5 출력 공통 필드

모든 지표는 가능한 경우 다음 메타데이터를 반환한다.

```json
{
  "metric_code": "RECOVERY_RATE_90D",
  "formula_version": "recovery_rate_v1",
  "value": 91.4,
  "unit": "PERCENT",
  "status": "OK",
  "sample_count": 7,
  "window_start": "2026-05-21",
  "window_end": "2026-08-18",
  "computed_at": "2026-08-18T06:00:00+09:00"
}
```

## 2. 지표 상태

| 상태 | 의미 |
|---|---|
| `OK` | 산식과 최소 계산 조건 충족 |
| `LOW_SAMPLE` | 계산은 했지만 표본이 해석 기준 미만 |
| `INSUFFICIENT_DATA` | 계산 불가 |
| `PARTIAL_PERIOD` | 현재 기간이 진행 중 |
| `SOURCE_DELAYED` | 원천 지연 |
| `NOT_COMPARABLE` | 면적·기간·정의 불일치 |
| `NOT_APPLICABLE` | 거래 유형상 적용 불가 |

## 3. 매매 중위가

### 코드

- `SALE_MEDIAN_30D`
- `SALE_MEDIAN_90D`
- formula: `sale_median_v1`

### 산식

```text
median(valid sale price_krw in area_scope and window)
```

### 표본

- 계산 최소: 1건
- 해석 권장: 3건 이상
- 순위 포함 기본: 3건 이상

1건이면 `LOW_SAMPLE`이다. `null`을 0원으로 반환하지 않는다.

## 4. 최신 유효 거래가

### 코드

- `LATEST_SALE_PRICE`
- formula: `latest_sale_v1`

### 선택 규칙

```text
ORDER BY contract_date DESC,
         source_last_modified_at DESC NULLS LAST,
         transaction_id DESC
LIMIT 1
```

같은 날짜에 여러 거래가 있으면 “최신가 하나”가 시장 대표 가격이라고 단정하지 않고 같은 날짜 거래 수를 함께 표시할 수 있다.

## 5. 역대 신고 최고가

### 코드

- `HISTORICAL_PEAK_SALE`
- formula: `historical_peak_v1`

### 산식

```text
max(valid sale price_krw through as_of_date within area_scope)
```

### 출력

- 최고가
- 계약일
- 동일 최고가 거래 수
- 해당 거래의 층과 품질 플래그

정정·취소로 최고가가 바뀌면 후속 계산에서 재평가한다. “시세 최고가”가 아니라 “수집된 유효 신고 거래 중 최고가”로 표현한다.

## 6. 최고가 회복률

### 코드

- `RECOVERY_RATE_90D`
- formula: `recovery_rate_v1`

### 산식

```text
최근 90일 매매 중위가 / 역대 신고 최고가 × 100
```

### 조건

- 90일 매매 표본 1건 이상
- 역대 최고가 존재
- 역대 최고가 > 0

### 상태

- 90일 표본 1~2건: `LOW_SAMPLE`
- 순위 기본 최소: 3건
- 최근 90일 신고가가 있으면 최대 100%가 될 수 있음

### 보조 지표

```text
LATEST_RECOVERY_RATE
= 최신 유효 매매가 / 역대 신고 최고가 × 100
```

두 지표를 혼용하지 않는다.

## 7. 거래량

### 코드

- `SALE_VOLUME_30D`
- `SALE_VOLUME_90D`
- formula: `transaction_volume_v1`

### 산식

```text
count(valid sale transactions in window)
```

거래량은 신고 건수이며 세대 회전율이 아니다. 중복 레코드와 취소 거래는 제외한다.

## 8. 거래량 모멘텀

### 코드

- `VOLUME_MOMENTUM_30D`
- formula: `volume_momentum_v1`

### 입력

- `current_count`: 최근 30일
- `previous_count`: 직전 30일

### 상태와 값

| 조건 | 상태 | ratio |
|---|---|---:|
| 이전 > 0, 최근 > 0 | `RATIO` | 최근/이전 |
| 이전 = 0, 최근 > 0 | `RESUMED` | `null` |
| 이전 > 0, 최근 = 0 | `STOPPED` | 0 |
| 이전 = 0, 최근 = 0 | `NO_ACTIVITY` | `null` |

분모가 0일 때 무한대 또는 임의의 큰 수로 정렬하지 않는다. 순위에서는 `RESUMED`를 별도 그룹으로 분리한다.

## 9. 전세 중위 보증금

### 코드

- `JEONSE_MEDIAN_90D`
- formula: `jeonse_median_v1`

### 산식

```text
median(valid JEONSE deposit_krw in same area_scope and 90-day window)
```

월세 거래는 포함하지 않는다. 갱신계약과 신규계약을 분리할 수 있는 원천에서는 기본 전체와 선택 필터를 모두 지원한다.

## 10. 전세가율

### 코드

- `JEONSE_RATIO_90D`
- formula: `jeonse_ratio_v1`

### 산식

```text
최근 90일 전세보증금 중위값
÷ 최근 90일 매매가 중위값
× 100
```

### 조건

- 동일 단지
- 동일 `area_scope`
- 동일 90일 창
- 매매·전세 각각 1건 이상

한쪽이 없으면 계산하지 않는다. 매매 1건 또는 전세 1건이면 `LOW_SAMPLE`이다.

## 11. 추정 매매·전세 갭

### 코드

- `ESTIMATED_GAP_90D`
- formula: `estimated_gap_v1`

### 산식

```text
최근 90일 매매가 중위값 - 최근 90일 전세보증금 중위값
```

### 표현 제한

- “추정 갭”으로만 부른다.
- 동일 동·층·향의 실제 짝이 아니다.
- 음수가 나오면 원천과 면적·기간 매핑을 품질 검사하며 자동으로 0으로 보정하지 않는다.
- 낮은 갭이 투자 안전성을 의미한다고 해석하지 않는다.

## 12. 신고가 이벤트

### 코드

- `NEW_HIGH`
- formula: `new_high_v1`

### 판정

거래 `T`에 대해:

```text
T.price_krw > max(valid prior sale price_krw
                  with contract_date < T.contract_date
                  in same area_scope)
```

동일 계약일의 순서에 의존하지 않는다. 동일 날짜 다수 거래가 기존 최고가를 함께 넘어선 경우 같은 기준 최고가에 대한 신고가 후보로 기록한다.

취소·정정으로 조건을 잃으면 신호를 `RETRACTED` 처리한다.

## 13. 가격 변화율

### 코드

- `SALE_MEDIAN_CHANGE`
- formula: `median_change_v1`

### 산식

```text
(현재 창 중위가 - 비교 창 중위가)
÷ 비교 창 중위가 × 100
```

두 창 모두 최소 1건이 필요하고 각각 3건 미만이면 `LOW_SAMPLE`이다. 서로 겹치지 않는 동일 길이 창을 기본으로 한다.

## 14. 단기 추세 후보

### 코드

- `SHORT_TERM_TREND_CANDIDATE`
- formula: `trend_candidate_v1`

### 상승 후보 조건

```text
A. 최근 30일 매매 중위가 >= 직전 90일 매매 중위가 × 1.03
B. 최근 30일 매매 거래량 >= 직전 30일 매매 거래량
C. 최근 90일 유효 매매 거래 >= 3건
D. 원천 상태가 UNAVAILABLE이 아님
```

### 결과

- 조건 모두 충족: `STARTED` 또는 `ACTIVE`
- 이후 미충족: `ENDED`
- 근거 거래 정정·취소: `RETRACTED` 가능

이 신호는 미래 가격 예측이 아니다. 응답은 “자체 산식상 단기 상승 추세 후보”로 표현한다.

## 15. 거래 재개 신호

### 코드

- `VOLUME_RESUMED`
- formula: `volume_resumed_v1`

### 조건

```text
직전 30일 유효 매매 0건
AND 최근 30일 유효 매매 >= 1건
```

표본 1건일 수 있으므로 가격 추세와 결합하지 않는다.

## 16. 지역 시장 펄스

### 코드

- `REGION_MARKET_PULSE`
- formula: `region_pulse_v1`

### 구성

- 최근/직전 기간 거래량
- 거래 단지 수
- 매매 중위가와 변화율
- 신고가 이벤트 수
- 거래 재개 단지 수
- 회복률 상위 단지
- 전세가율 분포
- 데이터 커버리지

지역 가격 중위가는 거래 건 전체 중위값이며 “평균 단지 가격”이 아니다. 특정 대단지의 거래 편중을 별도 경고한다.

## 17. 신뢰도

### 코드

- `DATA_CONFIDENCE`
- formula: `confidence_v1`

### 기본 등급

| 등급 | 최근 창 표본 | 추가 조건 |
|---|---:|---|
| `HIGH` | 5건 이상 | 지연 없음, 매핑 확정 |
| `MEDIUM` | 3~4건 | 중대한 품질 경고 없음 |
| `LOW` | 1~2건 | 계산 가능하나 해석 제한 |
| `INSUFFICIENT` | 0건 | 계산 불가 |

다음 조건은 한 단계 이상 낮출 수 있다.

- 원천 지연
- 현재 기간 미완결
- 매핑 신뢰도 낮음
- 취소·정정 비중 높음
- 단일 층 또는 특수층 거래 편중
- 한 거래가 중위값에 과도한 영향을 주는 작은 표본

## 18. 순위 규칙

- 기본 최소 표본: 3건
- `null`은 최하위가 아니라 순위 제외
- 동률은 같은 순위로 처리하고 안정적 2차 키 `complex_id` 사용
- 지표가 클수록 좋은지 낮을수록 좋은지 가치판단하지 않는다.
- “상위”는 해당 지표의 정렬 결과일 뿐 투자 우수 순위가 아니다.
- 모든 순위에 면적, 기간, 최소 표본, 산식 버전을 표시한다.

## 19. 산식 변경

산식 의미가 바뀌면 기존 `formula_version`을 수정하지 않는다.

```text
recovery_rate_v1 → recovery_rate_v2
```

새 버전은 `analytics.metric_definition`에 추가하고 재계산 범위, 전환일, 호환 정책을 기록한다. 과거 응답의 재현성을 위해 사용된 버전을 보존한다.
