# KR Apartment Market MCP Tool Specification v2.0

## 1. 목적

이 문서는 `kr-apartment-market-skill`에 내장된 FastMCP 서버의 전송, 인증, 공통 응답, canonical 도구, vendored 호환 계층과 오류 규약을 정의합니다. 기계 판독용 스키마는 `mcp/tool-definitions.json`이 기준입니다.

## 2. 실행

### stdio

```bash
kr-apartment-market --transport stdio
```

로컬 Codex·Claude Code·데스크톱 MCP 클라이언트에 적합합니다.

### Streamable HTTP

```bash
kr-apartment-market --transport streamable-http --host 0.0.0.0 --port 8765
```

공개 HTTP 배포에서 애플리케이션 앞단은 다음을 제공해야 합니다.

- HTTPS
- 사용자 또는 서비스 인증
- 요청량 제한
- 감사 로그
- secret redaction
- CORS/Origin 정책
- 관심 목록 사용자 격리

## 3. 환경 변수

| 변수 | 필수 | 기본값 | 용도 |
|---|---:|---|---|
| `DATA_GO_KR_API_KEY` | 거래 도구 사용 시 | 없음 | 국토교통부/공공데이터포털 서비스 키 |
| `ODCLOUD_API_KEY` | 청약 호환 도구 사용 시 | 없음 | 청약홈/ODCloud 서비스 키 |
| `TZ` | 아니오 | Asia/Seoul | 기준 시간대 |
| `KR_APARTMENT_HTTP_TIMEOUT` | 아니오 | 20 | 원천 호출 timeout 초 |
| `KR_APARTMENT_RETRY_COUNT` | 아니오 | 3 | 일시 오류 재시도 |
| `KR_APARTMENT_PAGE_SIZE` | 아니오 | 1000 | 원천 페이지 크기 |
| `KR_APARTMENT_MAX_PAGES` | 아니오 | 50 | 요청당 페이지 상한 |
| `KR_APARTMENT_MAX_MONTHS` | 아니오 | 60 | 요청당 월 상한 |
| `ENABLE_REAL_ESTATE_MCP_COMPAT` | 아니오 | true | vendored upstream 도구 등록 |
| `KR_APARTMENT_WATCHLIST_PATH` | 아니오 | 사용자 홈 아래 JSON | 로컬 관심 목록 |

## 4. 공통 응답

canonical 도구는 다음 envelope를 반환합니다.

```json
{
  "answered_at": "2026-08-21T19:00:00+09:00",
  "timezone": "Asia/Seoul",
  "data": {},
  "sources": [
    {
      "source": "국토교통부 실거래가 공개 API",
      "provider": "국토교통부/공공데이터포털",
      "lawd_code": "11680",
      "deal_months": ["202607", "202608"],
      "access": "API"
    }
  ],
  "notices": [
    "최신 신고·공개 실거래 기준이며 계약 취소·정정·신고 지연으로 변경될 수 있습니다."
  ]
}
```

`null`은 계산 불가 또는 원천 미제공입니다. 0원·0건과 의미가 다릅니다.

## 5. Canonical 도구

### `kr_apartment.resolve_location`

한국어 지역명 또는 코드를 LAWD_CD 후보로 변환합니다.

```json
{"query":"서울특별시 강남구","limit":5}
```

### `kr_apartment.get_transactions`

통합 실거래 조회입니다.

주요 입력:

- `lawd_code`: 5자리 코드 또는 해석 가능한 지역명
- `property_type`: apartment, officetel, villa, house, commercial
- `trade_type`: sale, rent
- `date_from`, `date_to`: YYYYMM, YYYY-MM, YYYY-MM-DD
- `complex_name`
- `area_m2`, `area_tolerance_m2`, `area_min_m2`, `area_max_m2`
- `include_canceled`, `include_raw`, `limit`

출력 거래에는 `source_record_id`, 계약일, 가격/보증금/월세, 면적, 취소 상태가 포함됩니다.

### `kr_apartment.search_complexes`

지역·기간의 아파트 매매 자료에 나타난 단지명을 검색합니다.

### `kr_apartment.get_complex_snapshot`

매매와 전세를 병렬 조회해 단지 스냅샷을 계산합니다.

- 90일 매매 중위값
- 90일 전세 중위값
- 조회 범위 최고가
- 회복률
- 전세가율
- 추정 갭
- 최근/직전 30일 거래량
- 표본 품질

### `kr_apartment.compare_complexes`

2~10개 단지를 같은 기간·면적 오차로 비교합니다.

```json
{
  "complexes": [
    {"lawd_code":"11680","complex_name":"A단지","area_m2":84.9},
    {"lawd_code":"11710","complex_name":"B단지","area_m2":84.8}
  ],
  "date_from":"2025-09",
  "date_to":"2026-08"
}
```

### `kr_apartment.get_region_pulse`

최근 30일과 직전 30일의 거래량·중위가격을 비교합니다.

### `kr_apartment.rank_complexes`

지원 지표:

```text
transaction_volume
median_price
recovery_rate
volume_momentum
jeonse_ratio
estimated_gap
```

### `kr_apartment.get_signal_feed`

`NEW_HIGH`와 `TRANSACTION_RESUMED` 신호를 반환합니다. 투자 신호가 아니라 데이터 조건 충족 이벤트입니다.

### `kr_apartment.get_data_freshness`

최신성 정의와 신고 지연·정정 가능성을 반환합니다.

### `kr_apartment.get_source_link`

`molit`, `apt2me`, `github` 링크를 반환합니다. Apt2Me는 기본 `LINK_OUT_ONLY`입니다.

### 금융 도구

```text
kr_apartment.calculate_loan_payment
kr_apartment.calculate_compound_growth
kr_apartment.calculate_monthly_cashflow
```

모든 결과는 가정 기반 산술 계산입니다.

### 관심 목록 도구

```text
kr_apartment.get_watchlist
kr_apartment.upsert_watchlist_item
kr_apartment.delete_watchlist_item
kr_apartment.get_watchlist_brief
```

로컬 JSON 어댑터는 단일 사용자 stdio 용도입니다. HTTP 다중 사용자에서는 DB/OAuth 어댑터로 교체합니다.

## 6. Vendored compatibility tools

`ENABLE_REAL_ESTATE_MCP_COMPAT=true`이면 `src/real_estate/`의 등록 함수를 같은 FastMCP 인스턴스에서 실행합니다. 이에 따라 원본 프로젝트의 다음 범주가 별도 설치 없이 노출됩니다.

- 지역 코드 검색
- 아파트·오피스텔·연립다세대·단독주택·상업용 매매
- 아파트·오피스텔·연립다세대·단독주택 전월세
- 아파트 청약 공고·결과
- 원리금·복리·현금흐름 계산

동일 목적이면 canonical `kr_apartment.*` 도구를 우선합니다. canonical 계층은 페이지네이션, 취소 보존, null 의미, 공통 envelope와 고수준 지표를 추가합니다.

## 7. 오류

| 오류 | 의미 | 조치 |
|---|---|---|
| `MISSING_DATA_GO_KR_API_KEY` | 거래 API 키 없음 | 환경 변수 설정 |
| `PUBLIC_DATA_RESPONSE_ERROR` | 원천 오류 또는 XML 해석 실패 | 응답 코드·범위 확인 |
| `PUBLIC_DATA_ERROR` | timeout·네트워크·재시도 소진 | 잠시 후 재시도 또는 범위 축소 |
| `ValueError: 지역명이 모호` | 후보가 여러 지역 | 5자리 코드 또는 완전한 지역명 사용 |
| 기간 상한 오류 | 60개월 초과 | 요청을 나눔 |
| 페이지 상한 오류 | 50페이지 초과 | 지역·월 범위를 축소 |

서버는 서비스 키를 오류 메시지에 포함하지 않습니다.

## 8. 데이터 정규화

```text
sale         → price_10k_krw
jeonse       → deposit_10k_krw, monthly_rent_10k_krw = 0 또는 null
monthly_rent → deposit_10k_krw + monthly_rent_10k_krw > 0
```

취소 판정은 원천의 해제 구분 또는 해제일을 이용합니다. 정확히 같은 source hash는 중복 제거하지만 취소 revision을 임의로 유효 거래와 합치지 않습니다.

## 9. 성능·호출 예산

- 월과 페이지는 순차 처리해 공공 API에 과도한 동시 요청을 보내지 않습니다.
- 단지 snapshot과 비교는 매매·전세만 병렬 처리합니다.
- 공개 운영에서는 지역·계약월 응답 캐시를 권장합니다.
- 캐시는 원천 이용 조건과 정정 반영 주기를 준수해야 합니다.

## 10. 프로토콜 검증

```bash
python scripts/validate_package.py . --write-manifest
pytest
kr-apartment-market --transport stdio
```

실제 원천 API smoke test와 Streamable HTTP inspector 절차는 `VALIDATION.md`를 따릅니다.
