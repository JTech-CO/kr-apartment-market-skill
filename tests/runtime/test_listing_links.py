from kr_apartment_market.home.listing_links import (
    build_listing_links,
    get_source_capabilities,
    inspect_listing_url,
)


def test_daangn_region_map_and_discovery_links():
    links = build_listing_links(
        region_name="경기도 용인시 수지구",
        complex_name="성복역롯데캐슬골드타운",
        transaction_type="sale",
        area_m2=84,
        sources=["daangn", "naver"],
    )
    daangn = next(item for item in links if item["source_id"] == "daangn")
    naver = next(item for item in links if item["source_id"] == "naver")
    assert daangn["link_type"] == "REGION_MAP"
    assert "/map/" in daangn["url"]
    assert "%EA%B2%BD%EA%B8%B0%EB%8F%84" in daangn["url"]
    assert "search.naver.com" in naver["discovery_url"]
    assert naver["listing_count"] is None


def test_inspect_known_and_unknown_urls():
    known = inspect_listing_url("https://fin.land.naver.com/articles/2531024266")
    assert known["recognized"] is True
    assert known["source_id"] == "naver"
    assert known["external_id"] == "2531024266"
    unknown = inspect_listing_url("https://example.com/listing/1")
    assert unknown["recognized"] is False


def test_source_capabilities_are_link_only():
    rows = get_source_capabilities()
    assert len(rows) >= 10
    assert all(row["access_mode"] == "LINK_OUT_ONLY" for row in rows)
    assert all(row["allow_contact_storage"] is False for row in rows)


def test_inspect_url_rejects_insecure_and_private_urls():
    import pytest

    with pytest.raises(ValueError, match="HTTPS"):
        inspect_listing_url("http://fin.land.naver.com/articles/1")
    with pytest.raises(ValueError, match="private"):
        inspect_listing_url("https://127.0.0.1/listing")
    with pytest.raises(ValueError, match="credentials"):
        inspect_listing_url("https://user:pass@fin.land.naver.com/articles/1")
