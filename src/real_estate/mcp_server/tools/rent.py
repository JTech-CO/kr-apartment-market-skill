"""Vendored compatibility tools for lease and monthly-rent records."""

from __future__ import annotations

from typing import Any

from kr_apartment_market.config import Settings
from kr_apartment_market.data.public_data import PublicDataClient, PublicDataError
from kr_apartment_market.mcp_compat import FastMCP
from real_estate.mcp_server._helpers import build_rent_summary


def _compat_item(tx: Any, kind: str) -> dict[str, Any]:
    result = {
        "unit_name": tx.complex_name or "",
        "dong": tx.dong or "",
        "area_sqm": tx.area_m2 or 0,
        "floor": tx.floor or 0,
        "deposit_10k": tx.deposit_10k_krw,
        "monthly_rent_10k": tx.monthly_rent_10k_krw or 0,
        "contract_type": tx.deal_type or "",
        "trade_date": tx.contract_date or "",
        "build_year": tx.build_year or 0,
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
            trade_type="rent",
            lawd_code=region_code,
            date_from=year_month,
            date_to=year_month,
            include_canceled=False,
        )
        items = [_compat_item(tx, kind) for tx in result.transactions[:num_of_rows]]
        return {
            "total_count": result.total_source_count,
            "items": items,
            "summary": build_rent_summary(items),
        }
    except PublicDataError as exc:
        return exc.to_dict()
    except (TypeError, ValueError) as exc:
        return {"error": "validation_error", "message": str(exc)}


def register_rent_tools(mcp: FastMCP, settings: Settings) -> list[str]:
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
        func.__doc__ = f"Return {kind} lease and monthly-rent records."
        mcp.tool(name=name)(func)
        names.append(name)

    register("get_apartment_rent", "apartment")
    register("get_officetel_rent", "officetel")
    register("get_villa_rent", "villa")
    register("get_single_house_rent", "house")
    return names
