from kr_apartment_market.data.regions import resolve_region


def test_exact_region_code():
    result = resolve_region("11680")
    assert result["matches"][0]["name"] == "서울특별시 강남구"


def test_full_region_name_is_unique():
    result = resolve_region("경기도 용인시 수지구")
    assert result["matches"] == [
        {"lawd_code": "41465", "name": "경기도 용인시 수지구"}
    ]


def test_ambiguous_short_name_returns_candidates():
    result = resolve_region("강서구")
    codes = {item["lawd_code"] for item in result["matches"]}
    assert {"11500", "26440"}.issubset(codes)
