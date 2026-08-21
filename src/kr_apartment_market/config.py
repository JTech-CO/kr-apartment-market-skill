"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class Settings:
    data_go_kr_api_key: str
    odcloud_api_key: str
    odcloud_service_key: str
    timezone: str
    http_timeout_seconds: int
    retry_count: int
    page_size: int
    max_pages: int
    max_months: int
    watchlist_path: Path
    enable_upstream_compat: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_go_kr_api_key=os.getenv("DATA_GO_KR_API_KEY", "").strip(),
            odcloud_api_key=os.getenv("ODCLOUD_API_KEY", "").strip(),
            odcloud_service_key=os.getenv("ODCLOUD_SERVICE_KEY", "").strip(),
            timezone=os.getenv("TZ", "Asia/Seoul").strip() or "Asia/Seoul",
            http_timeout_seconds=_int_env("KR_APARTMENT_HTTP_TIMEOUT", 20),
            retry_count=_int_env("KR_APARTMENT_RETRY_COUNT", 3, minimum=0),
            page_size=_int_env("KR_APARTMENT_PAGE_SIZE", 1000),
            max_pages=_int_env("KR_APARTMENT_MAX_PAGES", 50),
            max_months=_int_env("KR_APARTMENT_MAX_MONTHS", 60),
            watchlist_path=Path(
                os.getenv("KR_APARTMENT_WATCHLIST_PATH", ".data/watchlist.json")
            ).expanduser(),
            enable_upstream_compat=_bool_env("ENABLE_REAL_ESTATE_MCP_COMPAT", True),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
