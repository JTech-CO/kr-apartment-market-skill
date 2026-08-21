"""Compatibility tool registration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from kr_apartment_market.config import Settings
from kr_apartment_market.mcp_compat import FastMCP
from real_estate.mcp_server._region import search_region_code
from real_estate.mcp_server.tools.finance import register_finance_tools
from real_estate.mcp_server.tools.rent import register_rent_tools
from real_estate.mcp_server.tools.subscription import register_subscription_tools
from real_estate.mcp_server.tools.trade import register_trade_tools


def register_all(mcp: FastMCP, settings: Settings) -> list[str]:
    names: list[str] = []

    @mcp.tool(name="get_region_code")
    def get_region_code(query: str) -> dict[str, Any]:
        return search_region_code(query)

    names.append("get_region_code")

    @mcp.tool(name="get_current_year_month")
    def get_current_year_month() -> dict[str, str]:
        now = datetime.now(ZoneInfo(settings.timezone))
        return {"year_month": now.strftime("%Y%m")}

    names.append("get_current_year_month")
    names.extend(register_trade_tools(mcp, settings))
    names.extend(register_rent_tools(mcp, settings))
    names.extend(register_subscription_tools(mcp, settings))
    names.extend(register_finance_tools(mcp))
    return names


__all__ = ["register_all"]
