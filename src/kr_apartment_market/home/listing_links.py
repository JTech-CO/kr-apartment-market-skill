"""Policy-gated listing-source link generation.

This module deliberately does not scrape listing pages.  It creates verified
platform home/region links and a site-restricted discovery query so users can
open current advertisements at the original source.  User-supplied listing
URLs can be classified without downloading their content.
"""

from __future__ import annotations

import ipaddress
import json
import re
import urllib.parse
from importlib.resources import files
from typing import Any
from urllib.parse import urlparse

from kr_apartment_market.home.models import DEFAULT_LISTING_SOURCES

_TRANSACTION_LABELS = {
    "sale": "매매",
    "jeonse": "전세",
    "monthly_rent": "월세",
}


def load_listing_registry() -> dict[str, Any]:
    resource = files("kr_apartment_market.resources").joinpath("listing_sources.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def source_map() -> dict[str, dict[str, Any]]:
    registry = load_listing_registry()
    return {str(item["id"]): dict(item) for item in registry["sources"]}


def _query_terms(
    *,
    region_name: str | None,
    complex_name: str | None,
    transaction_type: str,
    area_m2: float | None,
) -> str:
    parts = [part.strip() for part in [region_name or "", complex_name or ""] if part.strip()]
    parts.append(_TRANSACTION_LABELS.get(transaction_type, transaction_type))
    if area_m2 is not None:
        parts.append(f"전용 {area_m2:g}㎡")
    parts.append("부동산 매물")
    return " ".join(parts)


def _site_search_url(domains: list[str], query: str) -> str:
    domain = domains[0]
    expression = f"site:{domain} {query}"
    return "https://search.naver.com/search.naver?" + urllib.parse.urlencode(
        {"where": "nexearch", "query": expression}
    )


def _region_link(source: dict[str, Any], region_name: str | None) -> tuple[str, str]:
    if source.get("regionLinkMode") == "PATH_REGION_MAP" and region_name:
        segments = [urllib.parse.quote(segment, safe="") for segment in region_name.split()]
        return f"{source['homepage'].rstrip('/')}/map/{'/'.join(segments)}", "REGION_MAP"
    return str(source["homepage"]), "PLATFORM_HOME"


def build_listing_links(
    *,
    region_name: str | None,
    complex_name: str | None,
    transaction_type: str,
    area_m2: float | None = None,
    sources: list[str] | None = None,
    property_type: str = "apartment",
) -> list[dict[str, Any]]:
    registry = source_map()
    selected = sources or list(DEFAULT_LISTING_SOURCES)
    query = _query_terms(
        region_name=region_name,
        complex_name=complex_name,
        transaction_type=transaction_type,
        area_m2=area_m2,
    )
    rows: list[dict[str, Any]] = []
    for source_id in selected:
        if source_id not in registry:
            raise ValueError(f"unknown listing source: {source_id}")
        source = registry[source_id]
        if property_type not in source.get("supportedPropertyTypes", []):
            continue
        primary_url, link_type = _region_link(source, region_name)
        rows.append(
            {
                "source_id": source_id,
                "source_name": source["name"],
                "access_mode": source["accessMode"],
                "link_type": link_type,
                "url": primary_url,
                "discovery_url": _site_search_url(source["domains"], query),
                "query_terms": query,
                "listing_count": None,
                "metadata_displayed": False,
                "notice": "광고가격·매물 상태는 원문 플랫폼에서 확인해야 합니다.",
            }
        )
    return rows


def get_source_capabilities(source_id: str | None = None) -> list[dict[str, Any]]:
    sources = source_map()
    if source_id is not None:
        if source_id not in sources:
            raise ValueError(f"unknown listing source: {source_id}")
        selected = [sources[source_id]]
    else:
        selected = list(sources.values())
    rows = []
    for item in selected:
        rows.append(
            {
                "source_id": item["id"],
                "source_name": item["name"],
                "homepage": item["homepage"],
                "category": item["category"],
                "access_mode": item["accessMode"],
                "supports_region_link": item["regionLinkMode"] != "HOME_ONLY",
                "supports_user_supplied_url": bool(item.get("supportsUserSuppliedUrl")),
                "supported_property_types": item.get("supportedPropertyTypes", []),
                "allow_metadata_display": False,
                "allow_metadata_storage": False,
                "allow_image_storage": False,
                "allow_contact_storage": False,
                "notes": item.get("notes"),
            }
        )
    rows.sort(key=lambda row: row["source_id"])
    return rows


def inspect_listing_url(url: str) -> dict[str, Any]:
    """Classify a user-supplied URL without fetching the remote page."""

    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("url must be an absolute HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url credentials are not allowed")
    host = parsed.hostname.casefold() if parsed.hostname else ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("private or non-public IP URLs are not allowed")
    matched: dict[str, Any] | None = None
    for source in source_map().values():
        if host in {domain.casefold() for domain in source["domains"]}:
            matched = source
            break
    if matched is None:
        return {
            "recognized": False,
            "url": url,
            "host": host,
            "access_mode": "UNREGISTERED_SOURCE",
            "notice": "등록되지 않은 원천입니다. 자동 수집이나 저장을 수행하지 않습니다.",
        }

    external_id = None
    entity_type = "PAGE"
    patterns = {
        "naver": [(r"/articles/(\d+)", "LISTING")],
        "daangn": [(r"/articles/(\d+)", "LISTING"), (r"/complexes/(\d+)", "COMPLEX")],
    }
    for pattern, kind in patterns.get(matched["id"], []):
        found = re.search(pattern, parsed.path)
        if found:
            external_id = found.group(1)
            entity_type = kind
            break
    return {
        "recognized": True,
        "source_id": matched["id"],
        "source_name": matched["name"],
        "url": url,
        "host": host,
        "entity_type": entity_type,
        "external_id": external_id,
        "access_mode": matched["accessMode"],
        "safe_actions": ["LINK_OUT", "USER_INITIATED_COMPARE"],
        "blocked_by_default": [
            "AUTOMATED_BULK_COLLECTION",
            "DESCRIPTION_STORAGE",
            "IMAGE_PROXY",
            "CONTACT_STORAGE",
        ],
        "notice": "URL 분류만 수행했으며 원격 페이지 내용은 가져오지 않았습니다.",
    }
