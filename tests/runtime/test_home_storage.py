from pathlib import Path

from kr_apartment_market.home.models import validate_search_profile
from kr_apartment_market.home.storage import HomeFinderStore


def profile():
    return validate_search_profile(
        {
            "profile_id": "profile-1",
            "name": "테스트",
            "transaction_type": "sale",
            "lawd_codes": ["11680"],
            "budget": {"max_price_10k_krw": 150000},
        }
    )[0]


def candidates(price=100000):
    return [
        {
            "lawd_code": "11680",
            "region_name": "서울특별시 강남구",
            "complex_name": "테스트단지",
            "transaction_type": "sale",
            "facts": {
                "reference_price_10k_krw": price,
                "transaction_count": 3,
                "latest_contract_date": "2026-08-01",
            },
            "score": {"match_score": 80, "confidence_score": 70},
        }
    ]


def test_saved_search_run_and_diff(tmp_path: Path):
    store = HomeFinderStore(tmp_path / "home.json")
    store.create_profile(profile())
    saved = store.save_search(profile_id="profile-1", search_id="search-1")
    assert saved["search_id"] == "search-1"
    assert store.diff_runs(None, candidates())[0]["type"] == "CANDIDATE_ADDED"
    previous = store.record_run(search_id="search-1", candidates=candidates())
    changes = store.diff_runs(previous, candidates(price=105000))
    types = {item["type"] for item in changes}
    assert "REFERENCE_PRICE_CHANGED" in types


def test_profile_delete_cascades_saved_search(tmp_path: Path):
    store = HomeFinderStore(tmp_path / "home.json")
    store.create_profile(profile())
    store.save_search(profile_id="profile-1", search_id="search-1")
    assert store.delete_profile("profile-1") is True
    assert store.get_saved_search("search-1") is None
