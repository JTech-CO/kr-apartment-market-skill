from pathlib import Path

import pytest

from kr_apartment_market.home.models import validate_search_profile
from kr_apartment_market.home.storage import HomeFinderStore


def base_profile() -> dict:
    return {
        "profile_id": "profile-1",
        "name": "수지 84 매매",
        "transaction_type": "sale",
        "lawd_codes": ["41465"],
        "region_names": {"41465": "경기도 용인시 수지구"},
        "budget": {"max_price_10k_krw": 90000},
        "area": {"min_m2": 82, "max_m2": 86},
        "building": {"max_age_years": 20, "min_parking_per_household": 1.0},
        "commute": [{"name": "판교역", "max_minutes": 45, "weight": 1}],
    }


def test_profile_normalization_and_warnings():
    profile, warnings = validate_search_profile(base_profile())
    assert profile["schema_version"] == "3.0.0"
    assert profile["lawd_codes"] == ["41465"]
    assert abs(sum(profile["weights"].values()) - 1.0) < 1e-6
    assert profile["hard_constraints"]["budget"] is True
    assert any("주차" in warning for warning in warnings)


def test_profile_rejects_invalid_region_code():
    payload = base_profile()
    payload["lawd_codes"] = ["not-code"]
    with pytest.raises(ValueError, match="lawd_code"):
        validate_search_profile(payload)


def test_profile_patch_preserves_created_at(tmp_path: Path):
    original, _ = validate_search_profile(base_profile())
    store = HomeFinderStore(tmp_path / "home.json")
    store.create_profile(original)
    updated, _ = validate_search_profile(
        {"profile_id": "profile-1", "budget": {"max_price_10k_krw": 85000}},
        existing=store.get_profile("profile-1"),
    )
    assert updated["created_at"] == original["created_at"]
    assert updated["budget"]["max_price_10k_krw"] == 85000
