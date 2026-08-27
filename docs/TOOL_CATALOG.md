# MCP Tool Catalog

Catalog version: `3.0.0`  
MCP target: `2026-07-28`  
Canonical tools: **32**

전체 JSON Schema는 `mcp/tool-definitions.json`을 기준으로 합니다.

| Tool | Title | Description |
|---|---|---|
| `kr_apartment.resolve_location` | 지역 코드 해석 | 한국어 지역명 또는 5/10자리 법정동 코드를 LAWD_CD 후보로 해석합니다. |
| `kr_apartment.get_transactions` | 통합 실거래 조회 | 국토교통부 공개 API에서 여러 부동산 유형의 매매·전월세 거래를 조회하고 정규화합니다. |
| `kr_apartment.search_complexes` | 단지 검색 | 지역과 기간의 아파트 매매 자료에서 단지명과 관측 면적 범위를 찾습니다. |
| `kr_apartment.get_complex_snapshot` | 단지 스냅샷 | 동일 면적 기준 매매·전세 중위값, 회복률, 전세가율, 추정 갭과 거래량을 계산합니다. |
| `kr_apartment.compare_complexes` | 단지 비교 | 2~10개 단지를 같은 기간과 면적 오차로 비교합니다. |
| `kr_apartment.get_region_pulse` | 지역 시장 펄스 | 최근 30일과 직전 30일의 거래량 및 중위가격을 비교합니다. |
| `kr_apartment.rank_complexes` | 단지 순위 | 지역 내 단지를 거래량·중위가·회복률·모멘텀·전세가율·추정 갭으로 정렬합니다. |
| `kr_apartment.get_signal_feed` | 시장 이벤트 | 신고가와 거래 재개 조건을 만족한 결정론적 이벤트를 반환합니다. |
| `kr_apartment.get_data_freshness` | 데이터 최신성 | 최신 신고 실거래의 의미와 한계를 설명합니다. |
| `kr_apartment.get_source_link` | 원문 링크 | 국토교통부·아파트Me·프로젝트 원문 링크를 반환합니다. 아파트Me는 LINK_OUT_ONLY입니다. |
| `kr_apartment.calculate_loan_payment` | 대출 상환 계산 | 입력 가정에 따른 원리금균등 또는 원금균등 상환액을 계산합니다. |
| `kr_apartment.calculate_compound_growth` | 복리 계산 | 초기 자산과 월 납입액의 가정 수익률 기반 복리 성장을 계산합니다. |
| `kr_apartment.calculate_monthly_cashflow` | 월 현금흐름 계산 | 소득·대출·생활비·기타 비용·임대수입을 이용해 월 현금흐름을 계산합니다. |
| `kr_apartment.get_watchlist` | 관심 목록 | 로컬 단일 사용자 관심 목록을 조회합니다. |
| `kr_apartment.upsert_watchlist_item` | 관심 단지 저장 | 관심 단지를 추가하거나 수정합니다. |
| `kr_apartment.delete_watchlist_item` | 관심 단지 삭제 | 관심 목록 항목을 삭제합니다. |
| `kr_apartment.get_watchlist_brief` | 관심 단지 브리핑 | 관심 단지의 현재 스냅샷을 조회합니다. |
| `kr_home.validate_search_profile` | 주거 선호 조건 검증 | 자연어에서 구조화된 주거 선호 프로필을 저장하지 않고 검증·정규화합니다. |
| `kr_home.create_search_profile` | 주거 탐색 프로필 생성 | 예산·지역·면적·가구·통근·가중치를 포함한 Home Finder 프로필을 저장합니다. |
| `kr_home.get_search_profile` | 주거 탐색 프로필 조회 | 프로필 하나를 조회하거나 저장된 전체 프로필을 나열합니다. |
| `kr_home.update_search_profile` | 주거 탐색 프로필 수정 | 기존 프로필을 부분 수정한 뒤 전체 계약을 다시 검증합니다. |
| `kr_home.delete_search_profile` | 주거 탐색 프로필 삭제 | 프로필과 연관 저장 검색·이전 실행 스냅샷을 삭제합니다. |
| `kr_home.recommend_complexes` | 조건 기반 단지 추천 | 국토교통부 실거래를 조회해 조건 적합도와 데이터 신뢰도를 분리하여 단지를 추천합니다. |
| `kr_home.explain_complex_match` | 단지 적합도 설명 | 미리 계산된 후보 사실에 동일한 결정론적 점수 모델을 적용하고 추천 이유·절충점·결측값을 설명합니다. |
| `kr_home.compare_candidates` | 후보 단지 비교 | 1~100개의 후보 사실을 같은 프로필과 산식으로 비교합니다. |
| `kr_home.find_listing_links` | 광고매물 원문 링크 | 네이버·당근·피터팬·아실·KB 등 원문 플랫폼의 지역 지도·홈·사이트 제한 검색 링크를 생성합니다. |
| `kr_home.get_listing_source_capabilities` | 광고매물 원천 정책 | 원천별 LINK_OUT_ONLY 정책과 허용·차단 데이터 처리 범위를 반환합니다. |
| `kr_home.inspect_listing_url` | 사용자 제공 매물 URL 분류 | 페이지를 내려받지 않고 사용자가 제공한 URL의 플랫폼·매물 식별자·허용 작업을 분류합니다. |
| `kr_home.save_search` | 주거 탐색 저장 | 프로필과 기간·후보 수를 재사용 가능한 저장 검색으로 기록합니다. |
| `kr_home.get_saved_searches` | 저장 검색 조회 | 전체 저장 검색 또는 특정 프로필의 저장 검색을 조회합니다. |
| `kr_home.delete_saved_search` | 저장 검색 삭제 | 저장 검색과 이전 실행 스냅샷을 삭제합니다. |
| `kr_home.get_search_updates` | 저장 검색 변경 브리핑 | 저장 검색을 다시 실행하고 후보 추가·제외, 순위·가격·거래 건수 변화를 기록합니다. |

## Namespaces

- `kr_apartment.*`: 실거래·시장 분석·금융 계산·관심 단지
- `kr_home.*`: 검색 프로필·추천·설명·광고매물 링크·저장 검색

## 호환 도구

`ENABLE_REAL_ESTATE_MCP_COMPAT=true`이면 저장소 내부의 `real_estate` 호환 도구 16개가 같은 FastMCP 서버에 추가됩니다. 호환 도구는 canonical 계약이 아니므로 신규 클라이언트는 `kr_apartment.*`와 `kr_home.*`를 우선 사용합니다.
