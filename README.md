# KR Apartment Market AI Skill

대한민국 부동산의 **최신 신고 실거래를 직접 조회하고**, 단지·지역 시장을 동일 기준으로 계산해 AI가 근거와 함께 설명하도록 만드는 오픈소스 **SKILL + 통합 MCP 서버**입니다.

![KR Apartment Market AI Skill](images/logo.png)

[소개 페이지](https://jtech-co.github.io/kr-apartment-market-skill/) · [PRD](PRD.md) · [MCP 명세](MCP_TOOL_SPEC.md) · [SKILL](SKILL.md) · [통합 설계](docs/REAL_ESTATE_MCP_INTEGRATION.md)

> 이 프로젝트에서 “실시간” 또는 “최신”은 주식 체결처럼 즉시 생성되는 가격이 아니라, 국토교통부 등 원천 시스템에 **최신으로 신고·공개된 거래**를 의미합니다. 신고 지연, 취소, 정정 때문에 결과가 바뀔 수 있습니다.

## v2.0: 설계 패키지에서 실행 가능한 서버로

v1은 PRD, SKILL, MCP 도구 계약, PostgreSQL 스키마를 중심으로 한 설계 패키지였습니다. v2는 MIT 라이선스의 [`tae0y/real-estate-mcp`](https://github.com/tae0y/real-estate-mcp)에서 검증된 공공데이터 실행 범위를 저장소 내부에 통합해, 별도 저장소나 별도 MCP 서버를 설치하지 않고 바로 실행할 수 있도록 확장했습니다.

- 국토교통부 실거래가 공개 API를 직접 호출하는 런타임 내장
- 아파트·오피스텔·연립다세대·단독/다가구·상업용 건물 지원
- 매매·전세·월세 거래 정규화
- 취소 거래를 삭제하지 않고 상태와 해제일 보존
- API 전체 페이지 순회, 재시도, 기간 상한, 표준 오류 처리
- 단지 스냅샷·비교·지역 펄스·순위·신고가 신호 계산
- 대출 상환액·복리·월 현금흐름 계산기 내장
- 청약홈/ODCloud 및 원본 도구 이름의 호환 계층 포함
- 로컬 관심 목록 저장소와 PostgreSQL 운영 설계 병행
- stdio·Streamable HTTP·Docker 실행 지원

`real-estate-mcp`의 소스는 `src/real_estate/`에 라이선스 고지와 함께 vendoring되어 있습니다. 사용자는 이 저장소 하나만 설치하면 됩니다. 원본 저작권과 MIT 전문은 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)와 [`licenses/real-estate-mcp-MIT.txt`](licenses/real-estate-mcp-MIT.txt)에 보존했습니다.

## 무엇을 할 수 있나

| 질문·작업 | 처리 방식 |
|---|---|
| “강남구 아파트 84㎡ 최근 실거래” | 법정동 코드 해석 → 국토교통부 API → 취소 거래 반영 → 표준 거래 모델 |
| “A단지와 B단지 중 어느 쪽이 회복됐나” | 같은 기간·전용면적·산식으로 중위가, 최고가 회복률, 거래량 비교 |
| “수지구 거래가 살아나는 단지” | 최근 30일과 직전 30일 거래량을 비교해 거래 재개·모멘텀 계산 |
| “전세가율과 추정 갭” | 동일 면적·동일 기간 매매/전세 중위값으로 결정론적 계산 |
| “최근 신고가 단지” | 최신 유효 거래와 그 이전 최고가를 계약일 순으로 비교 |
| “오피스텔·빌라·단독주택 거래” | 동일 MCP 서버의 통합 거래 도구에서 유형만 변경 |
| “청약 공고와 경쟁률” | vendored ApplyHome/ODCloud 호환 도구 사용 |
| “대출 원리금·임대 현금흐름” | 입력 가정만으로 계산하며 승인·수익을 보장하지 않음 |
| “관심 단지 브리핑” | 로컬 JSON 또는 PostgreSQL/OAuth 어댑터로 관심 목록 유지 |

## 아키텍처

```text
ChatGPT / Codex / Claude Code / MCP Client
                    │
                    ▼
      KR Apartment Market SKILL
      - 질문 해석·도구 선택·출력 규칙
                    │
                    ▼
      통합 FastMCP 서버 (이 저장소)
      ├─ 고수준 분석 도구: kr_apartment.*
      ├─ 공공데이터 직접 조회·정규화
      ├─ 결정론적 지표 엔진
      ├─ 로컬 관심 목록
      └─ real-estate-mcp 호환 도구
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 국토교통부/공공데이터포털   청약홈/ODCloud
          │
          ├─ 기본: 온디맨드, DB 불필요
          └─ 선택: PostgreSQL + Redis + OAuth
```

아파트Me는 서비스 기능과 사용자 경험을 참고하고, 사용자가 원문을 확인할 수 있는 링크를 제공하는 원천입니다. 자동 수집·저장·재배포는 별도 서면 권한이 확보되기 전까지 비활성화합니다. v2의 독립 실행 데이터 계층은 국토교통부와 공공데이터포털 API입니다.


### 오프라인 지역 코드 범위

배포물에는 전국 주요 시·군·구를 포함한 압축 5자리 LAWD_CD 표가 들어 있습니다. 패키지 표에 없는 지역도 사용자가 정확한 5자리 코드를 입력하면 조회할 수 있습니다. 전체 공식 법정동 표가 필요한 운영 환경은 `scripts/update_region_codes.py`로 공공 원천 또는 검증된 원본 TSV를 변환해 교체합니다.

## 빠른 시작

### 1. API 키 준비

공공데이터포털에서 필요한 국토교통부 실거래 API 활용 신청을 한 뒤 환경 변수를 설정합니다. 청약 도구를 쓰지 않는다면 `ODCLOUD_API_KEY`는 생략할 수 있습니다.

```bash
cp .env.example .env
# .env에서 DATA_GO_KR_API_KEY 입력
```

디코딩 키와 `%`가 포함된 인코딩 키를 모두 허용합니다. 키는 도구 응답과 일반 로그에 출력하지 않습니다.

### 2. 설치

```bash
# uv 권장
uv sync

# 또는 pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
python -m pip install -e .
```

### 3. stdio MCP 서버

```bash
uv run kr-apartment-market --transport stdio
```

저장소 루트의 `.mcp.json`은 이 명령을 사용하는 예시입니다.

### 4. Streamable HTTP

```bash
uv run kr-apartment-market \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8765
```

공개 배포에서는 TLS 종단, 인증, 호출량 제한, 원천 API 키 보호를 반드시 추가합니다.

### 5. Docker

```bash
docker compose up --build
```

## 고수준 도구

```text
kr_apartment.resolve_location
kr_apartment.get_transactions
kr_apartment.search_complexes
kr_apartment.get_complex_snapshot
kr_apartment.compare_complexes
kr_apartment.get_region_pulse
kr_apartment.rank_complexes
kr_apartment.get_signal_feed
kr_apartment.get_data_freshness
kr_apartment.get_source_link
kr_apartment.calculate_loan_payment
kr_apartment.calculate_compound_growth
kr_apartment.calculate_monthly_cashflow
kr_apartment.get_watchlist
kr_apartment.upsert_watchlist_item
kr_apartment.delete_watchlist_item
kr_apartment.get_watchlist_brief
```

`ENABLE_REAL_ESTATE_MCP_COMPAT=true`가 기본값이므로 원본 `real-estate-mcp`의 지역 조회, 유형별 거래, 청약, 금융 계산 도구도 같은 서버에 등록됩니다. 호환 도구를 숨기고 고수준 도구만 노출하려면 다음과 같이 실행합니다.

```bash
kr-apartment-market --transport stdio --no-upstream-compat
```

도구의 입력·출력 계약은 [`mcp/tool-definitions.json`](mcp/tool-definitions.json)과 [`MCP_TOOL_SPEC.md`](MCP_TOOL_SPEC.md)를 참조합니다.

## 데이터 처리 원칙

1. 최신 가격을 모델 기억으로 추측하지 않습니다.
2. 거래일, 수집일, 원천, 조회 월을 분리합니다.
3. 취소 거래는 원본에서 지우지 않고 `is_canceled`와 `canceled_at`으로 보존합니다.
4. 기본 통계에서는 취소 거래를 제외합니다.
5. 동일 전용면적을 우선하고 기본 허용 오차는 ±1㎡입니다.
6. 데이터가 없을 때 0원이나 0%로 대체하지 않고 `null`을 반환합니다.
7. 사실, 파생 지표, AI 해석을 구분합니다.
8. 전세가율이나 갭만으로 위험·수익을 단정하지 않습니다.
9. 투자, 감정평가, 세금, 대출 승인을 확정하거나 보장하지 않습니다.
10. 아파트Me 데이터는 승인 전까지 링크아웃만 허용합니다.

## 테스트와 검증

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src/kr_apartment_market tests/runtime
python scripts/validate_package.py . --write-manifest
```

런타임 테스트는 XML 파싱, 취소 거래 보존, 전세·월세 분류, 지표 계산, 금융 계산, 법정동 코드, 관심 목록 원자적 저장과 통합 도구 등록을 검증합니다. 원본 호환 동작도 `tests/runtime/`에서 함께 확인합니다.

## 저장소 구조

```text
.
├── SKILL.md
├── PRD.md
├── MCP_TOOL_SPEC.md
├── pyproject.toml
├── .mcp.json
├── src/
│   ├── kr_apartment_market/      # v2 고수준 통합 런타임
│   └── real_estate/              # vendored upstream compatibility layer
├── database/
│   ├── schema.sql
│   └── migrations/
├── mcp/tool-definitions.json
├── references/
├── evals/
├── tests/runtime/
├── docker/
├── licenses/
└── docs/
```

## 라이선스와 출처

프로젝트 전체는 MIT 라이선스입니다. `src/real_estate/`에 포함된 `real-estate-mcp` 파생 부분은 원 저작권자 `tae0y`의 MIT 조건을 따르며, 해당 고지를 삭제해서는 안 됩니다. 공개 데이터 자체의 이용 조건은 코드 라이선스와 별개이므로 각 원천의 이용약관, 호출 제한, 재배포 범위를 확인해야 합니다.

- 프로젝트 라이선스: [`LICENSE`](LICENSE)
- 제3자 고지: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- 원본 MIT 전문: [`licenses/real-estate-mcp-MIT.txt`](licenses/real-estate-mcp-MIT.txt)
- 통합 방식: [`docs/REAL_ESTATE_MCP_INTEGRATION.md`](docs/REAL_ESTATE_MCP_INTEGRATION.md)

## 상태

v2는 실행 가능한 Beta입니다. 공공 API의 실제 응답 필드와 운영 트래픽은 서비스별 승인 범위에 따라 달라질 수 있으므로, 공개 배포 전 [`VALIDATION.md`](VALIDATION.md)의 실 API·PostgreSQL·MCP 프로토콜 검증을 수행해야 합니다.
