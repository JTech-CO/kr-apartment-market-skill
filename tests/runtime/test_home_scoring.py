from datetime import date

from kr_apartment_market.home.models import CandidateFacts, validate_search_profile
from kr_apartment_market.home.scoring import score_candidate


def profile(**patch):
    raw = {
        "profile_id": "p",
        "transaction_type": "sale",
        "lawd_codes": ["41465"],
        "budget": {"max_price_10k_krw": 90000},
        "area": {"min_m2": 82, "max_m2": 86, "target_m2": 84},
        "building": {"max_age_years": 20, "min_parking_per_household": 1.0},
        "commute": [{"name": "판교역", "max_minutes": 45}],
        "preferences": {"preferred_jeonse_ratio_pct": 60},
    }
    raw.update(patch)
    return validate_search_profile(raw)[0]


def facts(price=85000, enrichment=None):
    return CandidateFacts(
        lawd_code="41465",
        region_name="경기도 용인시 수지구",
        complex_name="테스트센트럴",
        transaction_type="sale",
        reference_price_10k_krw=price,
        median_sale_price_10k_krw=price,
        median_jeonse_deposit_10k_krw=51000,
        latest_contract_date="2026-08-01",
        transaction_count=6,
        area_min_m2=84.7,
        area_max_m2=84.9,
        area_median_m2=84.8,
        representative_build_year=2015,
        recovery_rate_pct=94,
        jeonse_ratio_pct=60,
        estimated_gap_10k_krw=34000,
        enrichment=(
            {
            "commute_minutes": {"판교역": 38},
            "education_score": 78,
            "parking_per_household": 1.2,
            "listing_count": 8,
            }
            if enrichment is None
            else enrichment
        ),
    )


def test_explainable_score_and_confidence():
    result = score_candidate(profile(), facts(), as_of=date(2026, 8, 26))
    assert result.excluded is False
    assert result.match_score >= 80
    assert result.confidence_score >= 70
    assert any(component.name == "affordability" for component in result.components)
    assert result.strengths


def test_hard_budget_excludes_candidate():
    result = score_candidate(profile(), facts(price=95000), as_of=date(2026, 8, 26))
    assert result.excluded is True
    assert "최대 매매 예산 초과" in result.exclusion_reasons


def test_unknown_hard_parking_can_exclude():
    p = profile(unknown_policy="exclude", hard_constraints={"parking": True})
    result = score_candidate(p, facts(enrichment={}), as_of=date(2026, 8, 26))
    assert result.excluded is True
    assert any("세대당 주차" in reason for reason in result.exclusion_reasons)
