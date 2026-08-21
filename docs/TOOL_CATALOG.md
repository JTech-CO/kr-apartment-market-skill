# Tool Catalog v2.0

## Canonical tools — 17

### 탐색·조회

1. `kr_apartment.resolve_location`
2. `kr_apartment.get_transactions`
3. `kr_apartment.search_complexes`
4. `kr_apartment.get_complex_snapshot`
5. `kr_apartment.compare_complexes`
6. `kr_apartment.get_region_pulse`
7. `kr_apartment.rank_complexes`
8. `kr_apartment.get_signal_feed`
9. `kr_apartment.get_data_freshness`
10. `kr_apartment.get_source_link`

### 결정론적 금융 계산

11. `kr_apartment.calculate_loan_payment`
12. `kr_apartment.calculate_compound_growth`
13. `kr_apartment.calculate_monthly_cashflow`

### 관심 목록

14. `kr_apartment.get_watchlist`
15. `kr_apartment.upsert_watchlist_item`
16. `kr_apartment.delete_watchlist_item`
17. `kr_apartment.get_watchlist_brief`

## Vendored compatibility tools — 16

- `get_region_code`
- `get_current_year_month`
- `get_apartment_trades`
- `get_officetel_trades`
- `get_villa_trades`
- `get_single_house_trades`
- `get_commercial_trade`
- `get_apartment_rent`
- `get_officetel_rent`
- `get_villa_rent`
- `get_single_house_rent`
- `get_apt_subscription_info`
- `get_apt_subscription_results`
- `calculate_loan_payment`
- `calculate_compound_growth`
- `calculate_monthly_cashflow`

같은 목적이라면 공통 envelope, 취소 보존, 다중 월 조회와 고수준 지표를 제공하는 canonical 도구를 우선합니다.
