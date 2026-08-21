"""Upstream-compatible region lookup adapted to the packaged resolver."""

from __future__ import annotations

from typing import Any

from kr_apartment_market.data.regions import resolve_region


def search_region_code(query: str) -> dict[str, Any]:
    try:
        result = resolve_region(query, 10)
    except ValueError as exc:
        return {"error": "invalid_input", "message": str(exc)}
    matches = result.get("matches", [])
    if not matches:
        return {"error": "no_match", "message": f"No region found for: {query}"}
    first = matches[0]
    return {
        "region_code": first["lawd_code"],
        "full_name": first["name"],
        "matches": [
            {"code": f"{item['lawd_code']}00000", "name": item["name"]}
            for item in matches
        ],
    }
