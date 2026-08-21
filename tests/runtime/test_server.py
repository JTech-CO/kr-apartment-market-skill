from pathlib import Path

from kr_apartment_market.config import Settings
from kr_apartment_market.server import create_mcp


def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_go_kr_api_key="fixture-key",
        odcloud_api_key="",
        odcloud_service_key="",
        timezone="Asia/Seoul",
        http_timeout_seconds=5,
        retry_count=0,
        page_size=100,
        max_pages=5,
        max_months=12,
        watchlist_path=tmp_path / "watchlist.json",
        enable_upstream_compat=True,
    )


def test_canonical_tool_registration(tmp_path):
    _, names = create_mcp(settings=settings(tmp_path), enable_upstream_compat=False)
    assert len(names) == 17
    assert "kr_apartment.get_transactions" in names
    assert len(names) == len(set(names))


def test_integrated_compatibility_registration(tmp_path):
    _, names = create_mcp(settings=settings(tmp_path), enable_upstream_compat=True)
    assert len(names) == 33
    assert "get_apartment_trades" in names
    assert "get_apt_subscription_results" in names
