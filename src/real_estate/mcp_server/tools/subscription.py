"""Vendored compatibility tools for ApplyHome/ODCloud subscription data."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from kr_apartment_market.config import Settings
from kr_apartment_market.mcp_compat import FastMCP

_ODCLOUD_BASE_URL = "https://api.odcloud.kr/api"
_APT_SUBSCRIPTION_INFO_PATH = "/15101046/v1/uddi:14a46595-03dd-47d3-a418-d64e52820598"
_APPLYHOME_STAT_BASE_URL = "https://api.odcloud.kr/api/ApplyhomeStatSvc/v1"


def _auth(settings: Settings) -> tuple[dict[str, str], dict[str, Any]] | None:
    if settings.odcloud_api_key:
        return {"Authorization": settings.odcloud_api_key}, {}
    key = settings.odcloud_service_key or settings.data_go_kr_api_key
    if key:
        return {}, {"serviceKey": key}
    return None


async def _get_json(
    settings: Settings,
    url: str,
    *,
    headers: dict[str, str],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=float(settings.http_timeout_seconds)) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"error": "network_error", "message": "ODCloud 요청 또는 JSON 해석 실패"}
    if not isinstance(payload, dict):
        return {"error": "parse_error", "message": "Unexpected response type"}
    return payload


def register_subscription_tools(mcp: FastMCP, settings: Settings) -> list[str]:
    names: list[str] = []

    @mcp.tool(name="get_apt_subscription_info")
    async def get_apt_subscription_info(
        page: int = 1,
        per_page: int = 100,
        return_type: str = "JSON",
    ) -> dict[str, Any]:
        auth = _auth(settings)
        if auth is None:
            return {"error": "config_error", "message": "ODCLOUD API key is not set"}
        headers, secret_params = auth
        params: dict[str, Any] = {
            "page": page,
            "perPage": per_page,
            "returnType": return_type,
            **secret_params,
        }
        url = f"{_ODCLOUD_BASE_URL}{_APT_SUBSCRIPTION_INFO_PATH}?{urllib.parse.urlencode(params)}"
        payload = await _get_json(settings, url, headers=headers)
        if "error" in payload:
            return payload
        return {
            "total_count": int(payload.get("totalCount") or 0),
            "items": payload.get("data") or [],
            "page": int(payload.get("page") or page),
            "per_page": int(payload.get("perPage") or per_page),
            "current_count": int(payload.get("currentCount") or 0),
            "match_count": int(payload.get("matchCount") or 0),
        }

    names.append("get_apt_subscription_info")

    @mcp.tool(name="get_apt_subscription_results")
    async def get_apt_subscription_results(
        stat_kind: str,
        stat_year_month: str | None = None,
        area_code: str | None = None,
        reside_secd: str | None = None,
        page: int = 1,
        per_page: int = 100,
        return_type: str = "JSON",
    ) -> dict[str, Any]:
        endpoint_map = {
            "reqst_area": "getAPTReqstAreaStat",
            "reqst_age": "getAPTReqstAgeStat",
            "przwner_area": "getAPTPrzwnerAreaStat",
            "przwner_age": "getAPTPrzwnerAgeStat",
            "cmpetrt_area": "getAPTCmpetrtAreaStat",
            "aps_przwner": "getAPTApsPrzwnerStat",
        }
        endpoint = endpoint_map.get(stat_kind)
        if endpoint is None:
            return {"error": "validation_error", "message": "invalid stat_kind"}
        auth = _auth(settings)
        if auth is None:
            return {"error": "config_error", "message": "ODCLOUD API key is not set"}
        headers, secret_params = auth
        params: dict[str, Any] = {
            "page": page,
            "perPage": per_page,
            "returnType": return_type,
            **secret_params,
        }
        if stat_year_month:
            params["cond[STAT_DE::EQ]"] = stat_year_month
        if area_code:
            params["cond[SUBSCRPT_AREA_CODE::EQ]"] = area_code
        if reside_secd:
            params["cond[RESIDE_SECD::EQ]"] = reside_secd
        url = (
            f"{_APPLYHOME_STAT_BASE_URL}/{endpoint}?"
            f"{urllib.parse.urlencode(params)}"
        )
        payload = await _get_json(settings, url, headers=headers)
        if "error" in payload:
            return payload
        return {
            "stat_kind": stat_kind,
            "total_count": int(payload.get("totalCount") or 0),
            "items": payload.get("data") or [],
            "page": int(payload.get("page") or page),
            "per_page": int(payload.get("perPage") or per_page),
            "current_count": int(payload.get("currentCount") or 0),
            "match_count": int(payload.get("matchCount") or 0),
        }

    names.append("get_apt_subscription_results")
    return names
