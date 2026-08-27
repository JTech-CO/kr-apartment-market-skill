# Home Finder 점수 모델

모델 버전: `home-finder-3.0.0`

## 1. 목적

점수는 “투자 가치”나 “미래 가격”을 예측하지 않습니다. 사용자가 입력한 주거 조건과 확인 가능한 현재·과거 데이터를 비교해 **조건 적합도**를 계산합니다.

## 2. 두 개의 독립 값

### Match Score

확인 가능한 구성 요소를 사용자 가중치로 합산한 0~100 점수입니다.

```text
match_score
= Σ(component_score × normalized_available_weight)
```

### Confidence Score

전체 가중치 중 실제 데이터로 확인 가능한 비중과 표본 품질을 반영합니다.

```text
coverage = Σ(available component weight) / Σ(all component weight)
confidence_score = coverage × sample_quality × 100
```

따라서 적합도는 높지만 통근·주차·학군 정보가 없는 후보는 높은 `match_score`와 낮은 `confidence_score`를 동시에 가질 수 있습니다.

## 3. 기본 가중치

```yaml
affordability: 0.25
area_fit: 0.15
building_age: 0.08
liquidity: 0.12
recency: 0.10
recovery: 0.07
jeonse_safety: 0.05
commute: 0.08
education: 0.04
parking: 0.03
listing_availability: 0.03
```

프로필이 일부 가중치를 덮어쓰면 전체 합을 1로 정규화합니다.

## 4. 필수 조건

다음 조건은 점수 이전에 적용됩니다.

### 예산

매매는 `reference_price_10k_krw`, 전세는 보증금, 월세는 보증금과 월세를 각각 비교합니다.

### 면적

후보 거래의 면적 범위와 희망 면적 범위가 겹치지 않으면 제외합니다. 목표 면적이 있으면 tolerance를 적용합니다.

### 연식

대표 준공연도에서 기준연도를 빼 최대 연식을 초과하면 제외합니다.

### 최소 거래 표본

프로필의 `min_transaction_count`보다 유효 거래가 적으면 제외합니다.

### 선택형 필수 조건

통근·주차 등 enrichment 필드를 hard constraint로 지정한 경우, 값이 확인됐고 기준을 위반하면 제외합니다.

## 5. 구성 요소 산식

### 5.1 예산 적합도

상한만 있는 경우:

```text
price <= max: 100 - 20 × (price / max)
price > max: hard constraint라면 제외, 아니면 급격한 감점
```

하한·상한이 모두 있으면 범위 중앙과의 거리를 이용합니다. 예산을 지나치게 적게 쓰는 후보를 자동으로 나쁘다고 보지는 않되, 사용자가 최소 예산을 명시한 경우에만 반영합니다.

### 5.2 면적 적합도

목표 면적이 있으면:

```text
score = max(0, 100 - |candidate_median - target| / tolerance_scale × 100)
```

범위만 있으면 범위 안은 높은 점수, 경계 밖은 거리 비례 감점입니다.

### 5.3 건축 연식

최대 연식 내에서 신축에 가까울수록 완만하게 점수가 높아집니다. 연식이 없으면 unavailable입니다.

### 5.4 거래 유동성

최근 분석 기간의 유효 거래 수에 로그 스케일을 적용합니다. 1건과 5건의 차이는 크게, 50건과 60건의 차이는 작게 반영합니다.

### 5.5 최근성

최신 계약일과 `as_of`의 날짜 차이를 사용합니다.

```text
0~30일: 높음
31~90일: 완만한 감소
91~365일: 추가 감소
365일 초과: 낮음
```

### 5.6 회복률

동일 단지·동일 면적에 가까운 유효 거래의 최근 중위가와 역사적 최고가를 비교한 지표입니다. 회복률이 높다는 이유만으로 투자성이 높다고 해석하지 않습니다.

### 5.7 전세 안전성

전세 탐색에서 전세가율이 지나치게 높을수록 위험 신호로 감점할 수 있습니다. 이는 법적 안전성 판정이 아니라 가격 관계에 대한 보조 지표입니다.

### 5.8 통근

`enrichment.commute_minutes`가 있을 때만 계산합니다. 예상시간을 모델이 임의 생성하지 않습니다.

### 5.9 교육

학교 거리 또는 검증된 교육 지표가 있을 때만 사용합니다. 학업 성취를 보장하거나 학교를 서열화하는 문구는 피합니다.

### 5.10 주차

`parking_per_household`가 있을 때 사용자 차량 수·최소 주차 기준과 비교합니다.

### 5.11 매물 가용성

공식 제휴 데이터, 사용자 입력 또는 first-party feed로 확인된 `listing_count`만 사용합니다. 링크만 생성된 상태에서는 unavailable입니다.

## 6. 미확인 데이터 정책

```text
neutral  : 점수 분모에서 제외하고 confidence만 감소
penalize : 중립 이하의 보수적 점수 부여
exclude  : 필수로 취급해 후보 제외
```

기본값은 `neutral`입니다.

## 7. 출력 설명

각 구성 요소는 다음 계약을 따릅니다.

```json
{
  "name": "liquidity",
  "score": 72.5,
  "weight": 0.12,
  "available": true,
  "source": "MOLIT_TRANSACTION",
  "explanation": "분석 기간 유효 거래 8건을 기준으로 계산했습니다."
}
```

상위 구성 요소는 `strengths`, 낮은 구성 요소는 `tradeoffs`, 미확인은 `unknowns`에 요약합니다.

## 8. 재현성

다음 값이 같으면 점수 결과가 같아야 합니다.

- profile JSON
- candidate facts
- scoring model version
- `as_of`

AI 모델은 점수를 다시 계산하거나 수정하지 않고 도구가 반환한 값을 설명만 합니다.

## 9. 버전 관리

산식 또는 기본 가중치 변경 시 `home-finder-x.y.z` 버전을 올립니다. 저장 검색 비교에서는 서로 다른 major score model의 점수를 직접 증감 비교하지 않습니다.
