# 출력 계약

- 문서 버전: 1.0.0
- 기준일: 2026-08-18

## 1. 목적

이 문서는 MCP 구조화 결과와 최종 자연어 응답이 반드시 포함하거나 구분해야 할 필드, 경고, 숫자 표기, 오류 복구 방식을 정의한다.

## 2. 공통 MCP 결과

성공 결과는 `structuredContent`에 `outputSchema`를 통과하는 객체를 반환하고, 호환성을 위해 `content`에 짧은 텍스트 요약도 포함한다.

```json
{
  "resultType": "complete",
  "structuredContent": {
    "request_id": "req_01J...",
    "answered_at": "2026-08-18T21:20:00+09:00",
    "data": {},
    "freshness": {
      "status": "CURRENT",
      "source_watermark_at": "2026-08-18T05:10:00+09:00",
      "collected_at": "2026-08-18T05:18:24+09:00",
      "latest_contract_date": "2026-08-17",
      "is_partial_period": true
    },
    "sources": [],
    "warnings": []
  },
  "content": [
    {
      "type": "text",
      "text": "최신 신고 공개분 기준 결과입니다."
    }
  ],
  "isError": false
}
```

## 3. 공통 필수 객체

### 3.1 Freshness

```json
{
  "status": "CURRENT|PARTIAL|DELAYED|UNAVAILABLE|UNKNOWN",
  "source_watermark_at": "date-time|null",
  "collected_at": "date-time|null",
  "computed_at": "date-time|null",
  "latest_contract_date": "date|null",
  "is_partial_period": false,
  "coverage_note": "string|null"
}
```

### 3.2 Source reference

```json
{
  "source_code": "molit_public",
  "dataset_code": "MOLIT_APT_SALE",
  "display_name": "국토교통부 아파트 매매 실거래",
  "access_mode": "PUBLIC_OPEN",
  "content_ingested": true,
  "source_url": "https://...|null",
  "attribution": "string|null"
}
```

`apt2me`가 `LINK_OUT_ONLY`이면 `content_ingested`는 반드시 `false`다.

### 3.3 Warning

```json
{
  "code": "LOW_SAMPLE",
  "severity": "INFO|WARNING|ERROR",
  "message": "최근 90일 매매 표본이 2건뿐입니다.",
  "field": "metrics.recovery_rate_90d|null",
  "details": {}
}
```

## 4. 경고 코드

| 코드 | 기본 severity | 사용 시점 |
|---|---|---|
| `LOW_SAMPLE` | WARNING | 계산 표본이 해석 기준 미만 |
| `INSUFFICIENT_DATA` | WARNING | 필수 표본 없음 |
| `PARTIAL_PERIOD` | INFO | 현재 월·진행 중 기간 |
| `SOURCE_DELAYED` | WARNING | 원천 SLA 초과 |
| `SOURCE_UNAVAILABLE` | ERROR | 원천·캐시 모두 사용 불가 |
| `CANCELLATION_POSSIBLE` | INFO | 신고 취소·정정 가능성 고지 |
| `MAPPING_CONFIDENCE_LOW` | WARNING | 단지 매핑 불확실 |
| `AREA_NOT_COMPARABLE` | WARNING | 공통 면적 없음 |
| `OUTLIER_FLAGGED` | INFO | 품질 플래그가 있는 거래 포함 |
| `LINK_OUT_ONLY` | INFO | 링크 원천을 분석에 사용하지 않음 |
| `PARTNER_SOURCE_NOT_AUTHORIZED` | WARNING | 승인 어댑터 비활성 |

## 5. 최종 자연어 응답 구조

특정 단지 또는 비교 분석의 기본 구조:

```markdown
## 기준

- 대상: [지역 경로] [단지명]
- 전용면적: 84.97㎡
- 계약일 범위: 2026년 5월 21일~8월 18일
- 데이터 기준: 2026년 8월 18일 05:10 KST 원천 갱신분
- 원천: 국토교통부 공개 실거래
- 유효 표본: 매매 7건, 전세 5건
- 신뢰도: 높음

## 핵심 결과

사실 1~2문장과 제한적인 해석 1~2문장.

## 주요 지표

| 지표 | 값 | 계산 기준 |
|---|---:|---|
| 최신 유효 매매 | 12억 3,500만 원 | 계약일 ... |
| 최근 90일 중위가 | 12억 원 | 7건 |
| 역대 신고 최고가 | 13억 2,000만 원 | 유효 거래 전체 |
| 회복률 | 90.9% | 90일 중위가/역대 최고가 |
| 전세가율 | 54.2% | 동일 면적 90일 중위값 |
| 추정 갭 | 5억 5,000만 원 | 기간 중위값 차이 |

## 대표 거래

최대 5건.

## 해석

- 사실과 파생 지표에 근거한 조건부 설명
- 표본, 현재 기간, 지연, 취소 가능성 반영

## 주의사항

- 최신 체결 스트림이 아니라 최신 신고·공개분이다.
- 계약 취소·정정으로 수치가 바뀔 수 있다.
- 감정평가·투자·대출·세무 확정 자료가 아니다.

## 원문 확인

검증된 링크만 표시.
```

간단한 질의는 `기준 → 핵심 수치 → 한계`로 축약한다. 빈 섹션을 만들지 않는다.

## 6. 사실·지표·해석 문장 규칙

### 사실

```text
최근 30일 유효 매매 신고는 6건이고 직전 30일은 3건이다.
```

### 지표

```text
거래량 모멘텀은 2.0배다.
```

### 해석

```text
단기 거래 유동성이 늘어난 모습이다. 다만 현재 월 신고가 진행 중이므로 증가 폭은 달라질 수 있다.
```

해석 문장에 산식으로 확인되지 않은 원인, 정책 효과, 심리, 미래 가격을 사실처럼 추가하지 않는다.

## 7. 숫자 표기

### 가격

- 내부: KRW 정수 `1235000000`
- 사용자: `12억 3,500만 원`
- 표의 좁은 열: `12.35억 원` 허용, 본문에는 풀어 씀
- `null`: `자료 없음`
- 0원: 실제 0일 때만 `0원`

### 면적

- 기본: `전용 84.97㎡`
- 평 환산은 보조: `약 25.7평`
- 공급면적과 전용면적을 혼용하지 않음

### 비율

- 기본 소수점 한 자리
- 거래량 배수는 최대 소수점 두 자리
- 표본이 작으면 불필요한 정밀도를 줄임

### 날짜

- 사용자 응답: `2026년 8월 18일`
- 구조화 결과: ISO 8601
- 상대 날짜만 쓰지 않고 절대 날짜를 포함

## 8. 단지 비교 계약

- 비교 대상 2~5개
- 공통 면적·기간·필터 명시
- 항목별 결과를 나란히 표시
- “종합 1위”를 기본 생성하지 않음
- `NOT_COMPARABLE`인 대상은 수치 칸을 비우고 이유 표시
- 사용 목적이 명시되면 거래 유동성, 갭, 회복률 등 목적별 차이만 설명

## 9. 순위 계약

필수 표시:

- 지역
- 면적 범위
- 계약 기간
- 지표명과 산식 버전
- 정렬 방향
- 최소 표본
- 제외된 단지 수 또는 커버리지
- 현재 기간 여부

순위 제목은 “투자 가치 순위”가 아니라 “회복률 상위”, “거래량 상위”처럼 지표를 그대로 사용한다.

## 10. 오류 결과

도구 실행 오류는 `isError=true`와 안정적 오류 코드를 반환한다.

```json
{
  "resultType": "complete",
  "structuredContent": {
    "error": {
      "code": "AMBIGUOUS_LOCATION",
      "message": "동일한 단지명 후보가 여러 개입니다.",
      "retryable": false,
      "details": {
        "candidates": []
      }
    }
  },
  "content": [
    {
      "type": "text",
      "text": "지역을 포함해 단지를 선택해야 합니다."
    }
  ],
  "isError": true
}
```

LLM 회복 행동:

| 오류 | 행동 |
|---|---|
| `AMBIGUOUS_LOCATION` | 후보 최대 5개 제시 |
| `AREA_TYPE_NOT_FOUND` | 사용 가능한 면적 제시 |
| `QUERY_TOO_BROAD` | 지역·기간을 좁힘 |
| `INSUFFICIENT_DATA` | 표본 0/부족을 그대로 설명 |
| `SOURCE_DELAYED` | 마지막 정상 시각 표시 |
| `PARTNER_SOURCE_NOT_AUTHORIZED` | 공공 데이터 또는 link-out으로 전환 |
| `UNAUTHENTICATED` | 관심 목록만 로그인 필요하다고 설명 |

## 11. 원문 링크

- `get_source_link`가 반환한 URL만 사용
- 링크 제목에 원천명 표시
- 분석에 쓰지 않은 `LINK_OUT_ONLY` 원천은 “원문 확인”으로만 표현
- 링크가 없으면 URL을 추측하지 않음
- raw URL을 본문에 장황하게 나열하지 않고 의미 있는 링크 제목 사용

## 12. 금지 출력

- 근거 없는 미래 가격 목표
- “매수/매도 추천” 점수
- 다른 면적을 섞은 대표 가격
- 취소 거래 포함 여부가 불명확한 거래량
- 표본 없는 전세가율 또는 갭
- 민간 원천 데이터를 수집한 것처럼 보이는 문장
- 공개되지 않은 동·호 또는 거래 당사자 정보
- OAuth·API 비밀·내부 SQL·스택 트레이스

## 13. 최종 자체 점검

- [ ] 대상 ID와 지역 경로가 검증되었는가
- [ ] 면적과 기간이 명시되었는가
- [ ] 최신성 시각이 포함되었는가
- [ ] 취소 거래를 기본 제외했는가
- [ ] `null`과 0을 구분했는가
- [ ] 산식 버전 또는 기준을 설명했는가
- [ ] 표본 수와 신뢰도를 반영했는가
- [ ] 사실·지표·해석이 분리되었는가
- [ ] 투자·대출·세무 결과를 보장하지 않았는가
- [ ] 검증되지 않은 링크를 만들지 않았는가
