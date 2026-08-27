# 지표 및 추천 점수 정의

버전: 3.0.0

## 1. 공통 규칙

- 취소 거래 기본 제외
- 가격 내부 단위: 만 원
- 면적 내부 단위: ㎡
- 비교 기간과 면적 범위를 동일하게 유지
- 계산 불가 값은 `null`
- 산식 버전 기록

## 2. 시장 지표

### 최근 중위 매매가

```text
median_sale_price
= 기간·단지·면적 조건을 만족하는 유효 매매가격의 median
```

### 최근 중위 전세보증금

월세가 0인 임대차 또는 원천상 전세로 분류한 거래를 기본으로 사용합니다.

### 역대 최고가

```text
historical_peak
= 동일 단지·면적 그룹의 유효 매매 중 최고가격
```

### 회복률

```text
recovery_rate_pct
= 최근 기간 중위 매매가 / 역사적 최고가 × 100
```

최신 한 건이 아니라 중위값을 기본으로 사용해 특수층 거래의 영향을 줄입니다.

### 전세가율

```text
jeonse_ratio_pct
= 최근 전세보증금 중위값 / 최근 매매가 중위값 × 100
```

### 추정 갭

```text
estimated_gap
= 최근 매매가 중위값 - 최근 전세보증금 중위값
```

동일 동·층·향의 실제 쌍이 아니므로 “추정”으로 표시합니다.

### 거래량 모멘텀

```text
최근 30일 건수 / 직전 30일 건수
```

직전 기간 0건, 최근 기간 양수이면 `REOPENED`로 표현하고 무한대로 표시하지 않습니다.

### 신고가

현재 거래 이전의 최고가격보다 큰 유효 거래입니다.

## 3. Home Finder 기준 가격

```text
sale         → 기간 내 매매 중위가격
jeonse       → 기간 내 전세보증금 중위값
monthly_rent → 월세액 중위값 + 보증금 별도 표시
```

서로 다른 거래 유형의 가격을 같은 축으로 비교하지 않습니다.

## 4. Home Finder 점수

### 적합도

```text
match_score
= 이용 가능한 구성 요소 점수의 가중평균
```

### 신뢰도

```text
confidence_score
= 데이터 coverage × sample quality × recency quality × 100
```

### 구성 요소

| Code | 의미 | 원천 |
|---|---|---|
| `affordability` | 예산 적합도 | 실거래 |
| `area_fit` | 희망 면적 적합도 | 실거래 |
| `building_age` | 준공연도 적합도 | 거래 보조 필드 |
| `liquidity` | 유효 거래 표본 | 실거래 |
| `recency` | 최신 계약 경과일 | 실거래 |
| `recovery` | 최고가 회복률 | 파생 지표 |
| `jeonse_safety` | 전세가격 관계 | 파생 지표 |
| `commute` | 통근 조건 | enrichment |
| `education` | 교육·학교 조건 | enrichment |
| `parking` | 주차 조건 | enrichment |
| `listing_availability` | 확인된 광고매물 가용성 | 승인 원천·사용자 입력 |

## 5. 필수 조건

필수 조건은 score가 아니라 exclusion으로 처리합니다.

```text
EXCEEDS_MAX_BUDGET
BELOW_MIN_BUDGET
AREA_OUT_OF_RANGE
BUILDING_TOO_OLD
INSUFFICIENT_TRANSACTIONS
COMMUTE_CONSTRAINT_FAILED
PARKING_CONSTRAINT_FAILED
REQUIRED_DATA_UNKNOWN
```

## 6. 미확인 정책

- `neutral`: available weight에서 제외
- `penalize`: 보수적 점수
- `exclude`: 후보 제외

## 7. 광고가격 지표

승인된 동일 단지·동일 거래 유형·유사 면적 metadata가 있을 때만 계산합니다.

```text
asking_premium_pct
= asking_price_median / transaction_price_median × 100 - 100
```

링크만 있는 경우 계산하지 않습니다.
