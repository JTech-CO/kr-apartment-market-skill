"""Compatibility constants and summary helpers derived from real-estate-mcp."""

from __future__ import annotations

import statistics
from typing import Any

_APT_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
_APT_RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
_OFFI_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"
_OFFI_RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent"
_VILLA_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"
_VILLA_RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent"
_SINGLE_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade"
_SINGLE_RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent"
_COMMERCIAL_TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"


def build_trade_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [int(item["price_10k"]) for item in items if item.get("price_10k") is not None]
    return {
        "median_price_10k": int(statistics.median(prices)) if prices else 0,
        "min_price_10k": min(prices) if prices else 0,
        "max_price_10k": max(prices) if prices else 0,
        "sample_count": len(prices),
    }


def build_rent_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    deposits = [int(item["deposit_10k"]) for item in items if item.get("deposit_10k") is not None]
    rents = [int(item.get("monthly_rent_10k") or 0) for item in items]
    return {
        "median_deposit_10k": int(statistics.median(deposits)) if deposits else 0,
        "min_deposit_10k": min(deposits) if deposits else 0,
        "max_deposit_10k": max(deposits) if deposits else 0,
        "monthly_rent_avg_10k": int(statistics.mean(rents)) if rents else 0,
        "jeonse_ratio_pct": None,
        "sample_count": len(deposits),
    }
