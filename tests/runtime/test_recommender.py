from datetime import date

from kr_apartment_market.home.models import validate_search_profile
from kr_apartment_market.home.recommender import build_candidate_facts, rank_candidate_facts
from kr_apartment_market.models import Transaction


def sale(name: str, day: str, price: int, area: float, year: int) -> Transaction:
    return Transaction(
        source_record_id=f"s-{name}-{day}-{price}",
        source="fixture",
        property_type="apartment",
        trade_type="sale",
        lawd_code="41465",
        contract_date=day,
        complex_name=name,
        dong="성복동",
        area_m2=area,
        floor=10,
        build_year=year,
        price_10k_krw=price,
    )


def rent(name: str, day: str, deposit: int, monthly: int = 0) -> Transaction:
    return Transaction(
        source_record_id=f"r-{name}-{day}-{deposit}-{monthly}",
        source="fixture",
        property_type="apartment",
        trade_type="rent",
        lawd_code="41465",
        contract_date=day,
        complex_name=name,
        dong="성복동",
        area_m2=84.9,
        floor=10,
        build_year=2015,
        deposit_10k_krw=deposit,
        monthly_rent_10k_krw=monthly,
    )


def profile():
    return validate_search_profile(
        {
            "profile_id": "p",
            "transaction_type": "sale",
            "lawd_codes": ["41465"],
            "budget": {"max_price_10k_krw": 90000},
            "area": {"min_m2": 82, "max_m2": 86},
            "minimum_transactions": 2,
            "diversity_mode": "none",
        }
    )[0]


def test_candidate_build_and_ranking_filters_over_budget():
    sales = [
        sale("적합단지", "2026-06-01", 82000, 84.8, 2015),
        sale("적합단지", "2026-08-01", 85000, 84.9, 2015),
        sale("초과단지", "2026-06-01", 95000, 84.8, 2020),
        sale("초과단지", "2026-08-01", 98000, 84.9, 2020),
    ]
    rents = [rent("적합단지", "2026-08-02", 51000), rent("초과단지", "2026-08-02", 60000)]
    facts = build_candidate_facts(
        profile=profile(),
        lawd_code="41465",
        region_name="경기도 용인시 수지구",
        sales=sales,
        rents=rents,
        source_months=["202606", "202608"],
        as_of=date(2026, 8, 26),
    )
    result = rank_candidate_facts(
        profile=profile(),
        facts=facts,
        as_of=date(2026, 8, 26),
        include_excluded=True,
    )
    assert result["returned_count"] == 1
    assert result["candidates"][0]["complex_name"] == "적합단지"
    assert result["excluded_candidates"][0]["complex_name"] == "초과단지"
    assert result["candidates"][0]["listing_links"]
