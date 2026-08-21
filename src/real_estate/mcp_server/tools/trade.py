"""Vendored compatibility tools for property sale records."""

from __future__ import annotations

from typing import Any

from kr_apartment_market.config import Settings
from kr_apartment_market.data.public_data import PublicDataClient, PublicDataError
from kr_apartment_market.mcp_compat import FastMCP
from real_estate.mcp_server._helpers import build_trade_summary


def _compat_item(tx: Any, kind: str) -> dict[str, Any]:
    if kind == "commercial":
        return {
            "building_type": tx.house_type or "",
            "building_use": tx.complex_name or "",
            "land_use": (tx.raw or {}).get("landUse", ""),
            "dong": tx.dong or "",
            "building_ar": tx.area_m2 or 0,
            "floor": tx.floor or 0,
            "price_10k": tx.price_10k_krw,
            "trade_date": tx.contract_date or "",
            "build_year": tx.build_year or 0,
            "deal_type": tx.deal_type or "",
            "share_dealing": (tx.raw or {}).get("shareDealingType", ""),
        }
    name_key = "apt_name" if kind == "apartment" else "unit_name"
    result = {
        name_key: tx.complex_name or "",
        "dong": tx.dong or "",
        "area_sqm": tx.area_m2 or 0,
        "floor": tx.floor or 0,
        "price_10k": tx.price_10k_krw,
        "trade_date": tx.contract_date or "",
        "build_year": tx.build_year or 0,
        "deal_type": tx.deal_type or "",
    }
    if kind in {"villa", "house"}:
        result["house_type"] = tx.house_type or ""
    return result


async def _query(
    settings: Settings,
    *,
    kind: str,
    region_code: str,
    year_month: str,
    num_of_rows: int,
) -> dict[str, Any]:
    try:
        result = await PublicDataClient(settings).fetch_transactions(
            property_type=kind,  # type: ignore[arg-type]
            trade_type="sale",
            lawd_code=region_code,
            date_from=year_month,
            date_to=year_month,
            include_canceled=False,
        )
        items = [_compat_item(tx, kind) for tx in result.transactions[:num_of_rows]]
        return {
            "total_count": result.total_source_count,
            "items": items,
            "summary": build_trade_summary(items),
        }
    except PublicDataError as exc:
        return exc.to_dict()
    except (TypeError, ValueError) as exc:
        return {"error": "validation_error", "message": str(exc)}


def register_trade_tools(mcp: FastMCP, settings: Settings) -> list[str]:
    names: list[str] = []

    def register(name: str, kind: str):
        async def func(region_code: str, year_month: str, num_of_rows: int = 100):
            return await _query(
                settings,
                kind=kind,
                region_code=region_code,
                year_month=year_month,
                num_of_rows=num_of_rows,
            )

        func.__name__ = name
        func.__doc__ = f"Return {kind} sale records and summary statistics."
        mcp.tool(name=name)(func)
        names.append(name)

    register("get_apartment_trades", "apartment")
    register("get_officetel_trades", "officetel")
    register("get_villa_trades", "villa")
    register("get_single_house_trades", "house")
    register("get_commercial_trade", "commercial")
    return names
