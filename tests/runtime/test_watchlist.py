from kr_apartment_market.services.watchlist import WatchlistStore


def test_watchlist_roundtrip(tmp_path):
    store = WatchlistStore(tmp_path / "watchlist.json")
    item = store.upsert(
        profile_id="default",
        lawd_code="41465",
        complex_name="성복역롯데캐슬골드타운",
        area_m2=84,
    )
    assert len(store.list_items()) == 1
    assert store.delete(profile_id="default", item_id=item["id"]) is True
    assert store.list_items() == []
