"""Canonical KR Apartment Market MCP tool registration."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from kr_apartment_market.config import Settings
from kr_apartment_market.data.public_data import PublicDataClient, PublicDataError
from kr_apartment_market.data.regions import resolve_region
from kr_apartment_market.mcp_compat import FastMCP
from kr_apartment_market.models import PropertyType, SourceReference, TradeType, Transaction
from kr_apartment_market.services.finance import (
    calculate_compound_growth,
    calculate_loan_payment,
    calculate_monthly_cashflow,
)
from kr_apartment_market.services.metrics import (
    build_region_pulse,
    build_snapshot,
    detect_signals,
    group_by_complex,
    rank_complexes as calculate_rankings,
)
from kr_apartment_market.services.watchlist import WatchlistStore
from kr_apartment_market.utils import normalize_name, now_iso

_NOTICE = (
    "최신 신고·공개 실거래 기준이며 계약 취소·정정·신고 지연으로 결과가 변경될 수 있습니다."
)


def _source(lawd_code: str, months: list[str]) -> dict[str, Any]:
    return SourceReference(
        source="국토교통부 실거래가 공개 API",
        provider="국토교통부/공공데이터포털",
        lawd_code=lawd_code,
        deal_months=months,
    ).to_dict()


def _envelope(
    data: Any,
    settings: Settings,
    *,
    sources: list[dict[str, Any]] | None = None,
    notices: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "answered_at": now_iso(settings.timezone),
        "timezone": settings.timezone,
        "data": data,
        "sources": sources or [],
        "notices": notices or [],
    }


def _error_envelope(exc: Exception, settings: Settings) -> dict[str, Any]:
    if isinstance(exc, PublicDataError):
        error = exc.to_dict()
    else:
        error = {"error": type(exc).__name__, "message": str(exc)}
    return _envelope(None, settings, notices=[error["message"]]) | {"error": error}


def _lawd_code(value: str) -> str:
    if value.isdigit() and len(value) == 5:
        return value
    result = resolve_region(value, limit=10)
    matches = result.get("matches", [])
    if not matches:
        raise ValueError(f"지역을 찾지 못했습니다: {value}")
    if len(matches) > 1:
        names = ", ".join(f"{item['name']}({item['lawd_code']})" for item in matches[:5])
        raise ValueError(f"지역명이 모호합니다. 5자리 코드 또는 전체 지역명을 사용하세요: {names}")
    return str(matches[0]["lawd_code"])


def _tx_dicts(rows: list[Transaction], include_raw: bool, limit: int) -> list[dict[str, Any]]:
    return [row.to_dict(include_raw=include_raw) for row in rows[:limit]]


def register_canonical_tools(mcp: FastMCP, settings: Settings) -> list[str]:
    """Register canonical tools and return their names."""

    registered: list[str] = []

    def tool(name: str):
        def decorator(func):
            registered.append(name)
            return mcp.tool(name=name)(func)

        return decorator

    @tool("kr_apartment.resolve_location")
    def resolve_location(query: str, limit: int = 10) -> dict[str, Any]:
        """Resolve a Korean region name or legal-district code without network access."""
        try:
            return _envelope(resolve_region(query, limit), settings)
        except Exception as exc:  # tool boundary
            return _error_envelope(exc, settings)

    @tool("kr_apartment.get_transactions")
    async def get_transactions(
        lawd_code: str,
        property_type: PropertyType = "apartment",
        trade_type: TradeType = "sale",
        date_from: str | None = None,
        date_to: str | None = None,
        complex_name: str | None = None,
        area_m2: float | None = None,
        area_tolerance_m2: float = 1.0,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
        include_canceled: bool = False,
        include_raw: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Query and normalize MOLIT transactions across supported property types."""
        try:
            if limit < 1 or limit > 2000:
                raise ValueError("limit must be between 1 and 2000")
            code = _lawd_code(lawd_code)
            result = await PublicDataClient(settings).fetch_transactions(
                property_type=property_type,
                trade_type=trade_type,
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                complex_name=complex_name,
                area_m2=area_m2,
                area_tolerance_m2=area_tolerance_m2,
                area_min_m2=area_min_m2,
                area_max_m2=area_max_m2,
                include_canceled=include_canceled,
            )
            data = {
                "lawd_code": code,
                "property_type": property_type,
                "trade_type": trade_type,
                "deal_months": result.deal_months,
                "total_source_count": result.total_source_count,
                "matched_count": len(result.transactions),
                "returned_count": min(limit, len(result.transactions)),
                "transactions": _tx_dicts(result.transactions, include_raw, limit),
                "collected_at": result.collected_at,
            }
            return _envelope(data, settings, sources=[_source(code, result.deal_months)], notices=[_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.search_complexes")
    async def search_complexes(
        lawd_code: str,
        query: str = "",
        date_from: str | None = None,
        date_to: str | None = None,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search apartment complex names observed in MOLIT sale records."""
        try:
            code = _lawd_code(lawd_code)
            result = await PublicDataClient(settings).fetch_transactions(
                property_type="apartment",
                trade_type="sale",
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                area_min_m2=area_min_m2,
                area_max_m2=area_max_m2,
            )
            needle = normalize_name(query)
            groups = group_by_complex(result.transactions)
            rows = []
            for name, transactions in groups.items():
                if needle and needle not in normalize_name(name):
                    continue
                rows.append(
                    {
                        "complex_name": name,
                        "transaction_count": len(transactions),
                        "area_min_m2": min(
                            (tx.area_m2 for tx in transactions if tx.area_m2 is not None),
                            default=None,
                        ),
                        "area_max_m2": max(
                            (tx.area_m2 for tx in transactions if tx.area_m2 is not None),
                            default=None,
                        ),
                    }
                )
            rows.sort(key=lambda row: (-row["transaction_count"], row["complex_name"]))
            return _envelope(
                {"lawd_code": code, "complexes": rows[:limit]},
                settings,
                sources=[_source(code, result.deal_months)],
                notices=[_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    async def _snapshot(
        *,
        code: str,
        complex_name: str,
        date_from: str | None,
        date_to: str | None,
        area_m2: float | None,
        area_tolerance_m2: float,
    ) -> tuple[dict[str, Any], list[str]]:
        client = PublicDataClient(settings)
        sale_result, rent_result = await asyncio.gather(
            client.fetch_transactions(
                property_type="apartment",
                trade_type="sale",
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                complex_name=complex_name,
                area_m2=area_m2,
                area_tolerance_m2=area_tolerance_m2,
            ),
            client.fetch_transactions(
                property_type="apartment",
                trade_type="rent",
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                complex_name=complex_name,
                area_m2=area_m2,
                area_tolerance_m2=area_tolerance_m2,
            ),
        )
        data = {
            "lawd_code": code,
            "complex_name": complex_name,
            "area_m2": area_m2,
            "area_tolerance_m2": area_tolerance_m2,
            **build_snapshot(sale_result.transactions, rent_result.transactions),
        }
        months = sorted(set(sale_result.deal_months + rent_result.deal_months))
        return data, months

    @tool("kr_apartment.get_complex_snapshot")
    async def get_complex_snapshot(
        lawd_code: str,
        complex_name: str,
        date_from: str | None = None,
        date_to: str | None = None,
        area_m2: float | None = None,
        area_tolerance_m2: float = 1.0,
    ) -> dict[str, Any]:
        """Calculate a same-area apartment sale/rent snapshot."""
        try:
            code = _lawd_code(lawd_code)
            data, months = await _snapshot(
                code=code,
                complex_name=complex_name,
                date_from=date_from,
                date_to=date_to,
                area_m2=area_m2,
                area_tolerance_m2=area_tolerance_m2,
            )
            return _envelope(data, settings, sources=[_source(code, months)], notices=[_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.compare_complexes")
    async def compare_complexes(
        complexes: list[dict[str, Any]],
        date_from: str | None = None,
        date_to: str | None = None,
        area_tolerance_m2: float = 1.0,
    ) -> dict[str, Any]:
        """Compare 2-10 apartment complexes using identical periods and area tolerance."""
        try:
            if not 2 <= len(complexes) <= 10:
                raise ValueError("complexes must contain 2 to 10 items")
            tasks = []
            metadata = []
            for item in complexes:
                code = _lawd_code(str(item["lawd_code"]))
                name = str(item["complex_name"])
                area = float(item["area_m2"]) if item.get("area_m2") is not None else None
                metadata.append((code, name, area))
                tasks.append(
                    _snapshot(
                        code=code,
                        complex_name=name,
                        date_from=date_from,
                        date_to=date_to,
                        area_m2=area,
                        area_tolerance_m2=area_tolerance_m2,
                    )
                )
            results = await asyncio.gather(*tasks)
            rows = [data for data, _ in results]
            sources = [
                _source(code, months)
                for (code, _, _), (_, months) in zip(metadata, results, strict=True)
            ]
            return _envelope({"comparisons": rows}, settings, sources=sources, notices=[_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.get_region_pulse")
    async def get_region_pulse(
        lawd_code: str,
        date_from: str | None = None,
        date_to: str | None = None,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
    ) -> dict[str, Any]:
        """Compare the latest and previous 30-day sale windows for a region."""
        try:
            code = _lawd_code(lawd_code)
            if date_from is None:
                date_from = (date.today() - timedelta(days=90)).isoformat()
            result = await PublicDataClient(settings).fetch_transactions(
                property_type="apartment",
                trade_type="sale",
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                area_min_m2=area_min_m2,
                area_max_m2=area_max_m2,
            )
            data = {"lawd_code": code, **build_region_pulse(result.transactions)}
            return _envelope(data, settings, sources=[_source(code, result.deal_months)], notices=[_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.rank_complexes")
    async def rank_complexes(
        lawd_code: str,
        metric: str = "transaction_volume",
        date_from: str | None = None,
        date_to: str | None = None,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Rank apartment complexes by a deterministic market metric."""
        try:
            if metric not in {
                "transaction_volume",
                "median_price",
                "recovery_rate",
                "volume_momentum",
                "jeonse_ratio",
                "estimated_gap",
            }:
                raise ValueError("unsupported metric")
            code = _lawd_code(lawd_code)
            client = PublicDataClient(settings)
            sales, rents = await asyncio.gather(
                client.fetch_transactions(
                    property_type="apartment",
                    trade_type="sale",
                    lawd_code=code,
                    date_from=date_from,
                    date_to=date_to,
                    area_min_m2=area_min_m2,
                    area_max_m2=area_max_m2,
                ),
                client.fetch_transactions(
                    property_type="apartment",
                    trade_type="rent",
                    lawd_code=code,
                    date_from=date_from,
                    date_to=date_to,
                    area_min_m2=area_min_m2,
                    area_max_m2=area_max_m2,
                ),
            )
            rows = calculate_rankings(
                sales.transactions, rents.transactions, metric=metric, limit=limit
            )
            months = sorted(set(sales.deal_months + rents.deal_months))
            return _envelope(
                {"lawd_code": code, "metric": metric, "rankings": rows},
                settings,
                sources=[_source(code, months)],
                notices=[_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.get_signal_feed")
    async def get_signal_feed(
        lawd_code: str,
        date_from: str | None = None,
        date_to: str | None = None,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return deterministic NEW_HIGH and TRANSACTION_RESUMED events."""
        try:
            code = _lawd_code(lawd_code)
            result = await PublicDataClient(settings).fetch_transactions(
                property_type="apartment",
                trade_type="sale",
                lawd_code=code,
                date_from=date_from,
                date_to=date_to,
                area_min_m2=area_min_m2,
                area_max_m2=area_max_m2,
            )
            signals = detect_signals(result.transactions)[:limit]
            return _envelope(
                {"lawd_code": code, "signals": signals},
                settings,
                sources=[_source(code, result.deal_months)],
                notices=[_NOTICE, "이벤트는 투자 신호나 가격 예측이 아닙니다."],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.get_data_freshness")
    def get_data_freshness() -> dict[str, Any]:
        """Describe the meaning and limitations of latest reported transactions."""
        return _envelope(
            {
                "definition": "원천 시스템에 최신으로 신고·공개된 거래",
                "not_streaming_price": True,
                "contract_date_is_distinct_from_collection_time": True,
                "possible_changes": ["신고 지연", "계약 취소", "정정 신고", "원천 재처리"],
            },
            settings,
            notices=[_NOTICE],
        )

    @tool("kr_apartment.get_source_link")
    def get_source_link(
        source: str = "molit",
        entity_type: str = "home",
        lawd_code: str | None = None,
    ) -> dict[str, Any]:
        """Return verified source or project links without scraping the target."""
        links = {
            "molit": "https://rt.molit.go.kr/",
            "apt2me": "https://apt2.me/",
            "github": "https://github.com/JTech-CO/kr-apartment-market-skill",
            "landing": "https://jtech-co.github.io/kr-apartment-market-skill/",
        }
        if source not in links:
            return _error_envelope(ValueError("unsupported source"), settings)
        access_type = "LINK_OUT_ONLY" if source == "apt2me" else "LINK"
        return _envelope(
            {
                "source": source,
                "entity_type": entity_type,
                "lawd_code": lawd_code,
                "url": links[source],
                "access_type": access_type,
            },
            settings,
        )

    @tool("kr_apartment.calculate_loan_payment")
    def loan_payment(
        principal_10k: float,
        annual_rate_pct: float,
        years: int,
        repayment_method: str = "equal_payment",
    ) -> dict[str, Any]:
        try:
            return _envelope(
                calculate_loan_payment(
                    principal_10k, annual_rate_pct, years, repayment_method
                ),
                settings,
                notices=["가정 기반 산술 결과이며 실제 대출 승인·금리·한도를 보장하지 않습니다."],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.calculate_compound_growth")
    def compound_growth(
        initial_10k: float,
        monthly_contribution_10k: float,
        annual_rate_pct: float,
        years: int,
    ) -> dict[str, Any]:
        try:
            return _envelope(
                calculate_compound_growth(
                    initial_10k, monthly_contribution_10k, annual_rate_pct, years
                ),
                settings,
                notices=["가정한 수익률에 따른 계산이며 실제 수익을 보장하지 않습니다."],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.calculate_monthly_cashflow")
    def monthly_cashflow(
        monthly_income_10k: float,
        monthly_loan_payment_10k: float,
        monthly_living_cost_10k: float,
        other_monthly_costs_10k: float = 0,
        monthly_rent_income_10k: float = 0,
    ) -> dict[str, Any]:
        try:
            return _envelope(
                calculate_monthly_cashflow(
                    monthly_income_10k,
                    monthly_loan_payment_10k,
                    monthly_living_cost_10k,
                    other_monthly_costs_10k,
                    monthly_rent_income_10k,
                ),
                settings,
                notices=["세금·공실·수선비 등 실제 비용을 별도로 검토해야 합니다."],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    def store() -> WatchlistStore:
        return WatchlistStore(settings.watchlist_path, settings.timezone)

    @tool("kr_apartment.get_watchlist")
    def get_watchlist(profile_id: str = "default") -> dict[str, Any]:
        try:
            return _envelope(
                {"profile_id": profile_id, "items": store().list_items(profile_id)},
                settings,
                notices=["로컬 JSON 관심 목록은 단일 사용자 stdio 환경용입니다."],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.upsert_watchlist_item")
    def upsert_watchlist_item(
        lawd_code: str,
        complex_name: str,
        profile_id: str = "default",
        area_m2: float | None = None,
        label: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            code = _lawd_code(lawd_code)
            item = store().upsert(
                profile_id=profile_id,
                lawd_code=code,
                complex_name=complex_name,
                area_m2=area_m2,
                label=label,
                item_id=item_id,
            )
            return _envelope({"profile_id": profile_id, "item": item}, settings)
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.delete_watchlist_item")
    def delete_watchlist_item(item_id: str, profile_id: str = "default") -> dict[str, Any]:
        try:
            return _envelope(
                {
                    "profile_id": profile_id,
                    "item_id": item_id,
                    "deleted": store().delete(profile_id=profile_id, item_id=item_id),
                },
                settings,
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_apartment.get_watchlist_brief")
    async def get_watchlist_brief(
        profile_id: str = "default",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Fetch current snapshots for up to 20 local watchlist entries."""
        try:
            items = store().list_items(profile_id)[: min(limit, 20)]
            tasks = [
                _snapshot(
                    code=item["lawd_code"],
                    complex_name=item["complex_name"],
                    date_from=date_from,
                    date_to=date_to,
                    area_m2=item.get("area_m2"),
                    area_tolerance_m2=1.0,
                )
                for item in items
            ]
            results = await asyncio.gather(*tasks) if tasks else []
            briefs = []
            sources = []
            for item, (snapshot, months) in zip(items, results, strict=True):
                briefs.append({"watchlist_item": item, "snapshot": snapshot})
                sources.append(_source(item["lawd_code"], months))
            return _envelope(
                {"profile_id": profile_id, "briefs": briefs},
                settings,
                sources=sources,
                notices=[_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    return registered
