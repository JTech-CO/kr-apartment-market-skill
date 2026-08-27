# Validation Report — KR Apartment Market AI Skill v3.0.0

검증일: 2026-08-26  
대상: AI Home Finder 통합 소스 패키지

## 결과 요약

| 검증 항목 | 결과 |
|---|---|
| Home Finder 포함 runtime test | 28개 통과 |
| Python source compile | 통과 |
| 정적 package validator | 전체 통과 |
| canonical MCP catalog/runtime | 32개 일치 |
| vendored compatibility 포함 | 48개 등록 |
| 광고매물 source registry | 11개 확인 |
| 기본 source access mode | 전부 `LINK_OUT_ONLY` |
| HTTPS·credential·private-IP URL guard | 통과 |
| PostgreSQL finder/listing 정적 invariant | 통과 |
| listing observation authorization trigger | 확인 |
| upstream MIT 고지 | 확인 |
| hardcoded API key·local user data | 발견되지 않음 |
| wheel build | 통과 (`--no-build-isolation`) |
| wheel resource content | 통과 |
| wheel target-install smoke test | 통과 |
| 소개 페이지 v3·OG·GitHub link | 통과 |

## Runtime test

```text
28 passed
```

포함 범위:

- 거래·임대차 XML fixture parser
- 취소 거래와 market metric
- 금융 계산
- 관심 목록
- Home Finder profile validation
- hard constraints
- match/confidence score
- 후보 생성·순위·listing links
- 사용자 URL 안전
- 저장 검색·run diff
- 32/48 MCP tool registration

## 정적 validator

`python scripts/validate_package.py . --write-manifest` 결과 모든 check가 통과했습니다.

주요 확인값:

```text
package version       3.0.0
canonical tools       32
integrated tools      48
offline region rows  250
listing sources       11
Home Finder evals     25
```

## Wheel

생성 파일:

```text
kr_apartment_market_skill-3.0.0-py3-none-any.whl
```

확인한 package data:

```text
kr_apartment_market/resources/region_codes.tsv
kr_apartment_market/resources/listing_sources.json
real_estate/resources/region_codes.txt
real_estate/LICENSE
```

격리 빌드는 실행 환경의 외부 네트워크 차단으로 build dependency를 다시 내려받지 못했습니다. 설치되어 있던 `setuptools 82.0.1`과 `wheel 0.46.3`을 사용하는 `--no-build-isolation` 방식으로 wheel을 빌드했습니다.

## 설치 smoke test

wheel을 별도 target directory에 `--no-deps`로 설치한 뒤 현재 실행 환경의 dependency를 사용해 확인했습니다.

```text
version             3.0.0
canonical tools     32
integrated tools    48
listing sources     11
```

## SQL

정적 확인:

- `finder` schema
- `listing` schema
- search profile·version·saved search·run·candidate·component
- source registry·source policy·discovery link·user URL
- authorized listing observation·cluster·change event
- RLS·FORCE RLS
- link-only source에 metadata 저장을 막는 trigger

현재 실행 환경에는 연결된 PostgreSQL 16 instance가 없어 DDL의 실제 migration 실행은 수행하지 않았습니다. 운영 배포 전 `VALIDATION.md` 절차로 staging DB에 적용해야 합니다.

## 라이브 공공 API

유효한 `DATA_GO_KR_API_KEY`, `ODCLOUD_API_KEY`가 제공되지 않아 국토교통부·청약홈 서버를 대상으로 한 live call은 수행하지 않았습니다. 네트워크를 제외한 parser, normalization, metric, scoring, link policy와 MCP registration은 fixture·정적 검사로 검증했습니다.

## Lint

`ruff` 실행 모듈은 현재 환경에 설치되어 있지 않아 별도 lint command는 수행하지 않았습니다. Python compile과 runtime test는 통과했으며, CI 환경에서는 `uv sync --extra dev && uv run ruff check src tests/runtime scripts`를 실행하도록 권장합니다.
