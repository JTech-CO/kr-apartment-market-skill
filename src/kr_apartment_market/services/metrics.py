"""Deterministic market metrics; the LLM must not recompute these values."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from kr_apartment_market.models import Transaction
from kr_apartment_market.utils import normalize_name


def _median(values: Iterable[int | float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return float(statistics.median(clean)) if clean else None


def _date(tx: Transaction) -> date | None:
    try:
        return date.fromisoformat(tx.contract_date) if tx.contract_date else None
    except ValueError:
        return None


def quality_grade(sample_count: int) -> str:
    if sample_count >= 5:
        return "HIGH"
    if sample_count >= 2:
        return "MEDIUM"
    if sample_count == 1:
        return "LOW"
    return "INSUFFICIENT"


def build_snapshot(
    sales: list[Transaction],
    rents: list[Transaction],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    valid_sales = [tx for tx in sales if not tx.is_canceled and tx.price_10k_krw is not None]
    valid_rents = [tx for tx in rents if not tx.is_canceled and tx.deposit_10k_krw is not None]
    valid_sales.sort(key=lambda tx: (tx.contract_date or "", tx.source_record_id), reverse=True)
    valid_rents.sort(key=lambda tx: (tx.contract_date or "", tx.source_record_id), reverse=True)

    sale_median = _median(tx.price_10k_krw for tx in valid_sales)
    peak = max((tx.price_10k_krw for tx in valid_sales if tx.price_10k_krw is not None), default=None)
    jeonse = [
        tx
        for tx in valid_rents
        if tx.monthly_rent_10k_krw in {None, 0}
        and tx.deposit_10k_krw is not None
    ]
    jeonse_median = _median(tx.deposit_10k_krw for tx in jeonse)

    recovery = (
        round(float(sale_median) / float(peak) * 100, 2)
        if sale_median is not None and peak not in {None, 0}
        else None
    )
    jeonse_ratio = (
        round(float(jeonse_median) / float(sale_median) * 100, 2)
        if jeonse_median is not None and sale_median not in {None, 0}
        else None
    )
    estimated_gap = (
        round(float(sale_median) - float(jeonse_median), 2)
        if sale_median is not None and jeonse_median is not None
        else None
    )

    recent_start = as_of - timedelta(days=29)
    previous_start = as_of - timedelta(days=59)
    previous_end = recent_start - timedelta(days=1)
    recent = [tx for tx in valid_sales if (_date(tx) or date.min) >= recent_start]
    previous = [
        tx
        for tx in valid_sales
        if previous_start <= (_date(tx) or date.min) <= previous_end
    ]
    if previous:
        volume_momentum: float | str | None = round(len(recent) / len(previous), 4)
    elif recent:
        volume_momentum = "REOPENED"
    else:
        volume_momentum = None

    return {
        "latest_sale": valid_sales[0].to_dict() if valid_sales else None,
        "latest_rent": valid_rents[0].to_dict() if valid_rents else None,
        "sale_sample_count": len(valid_sales),
        "rent_sample_count": len(valid_rents),
        "jeonse_sample_count": len(jeonse),
        "median_sale_price_10k_krw": round(sale_median, 2) if sale_median is not None else None,
        "historical_peak_10k_krw": peak,
        "recovery_rate_pct": recovery,
        "median_jeonse_deposit_10k_krw": (
            round(jeonse_median, 2) if jeonse_median is not None else None
        ),
        "jeonse_ratio_pct": jeonse_ratio,
        "estimated_gap_10k_krw": estimated_gap,
        "recent_30d_sale_count": len(recent),
        "previous_30d_sale_count": len(previous),
        "volume_momentum": volume_momentum,
        "quality": quality_grade(len(valid_sales)),
        "as_of": as_of.isoformat(),
    }


def build_region_pulse(sales: list[Transaction], *, as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    valid = [tx for tx in sales if not tx.is_canceled and tx.price_10k_krw is not None]
    recent_start = as_of - timedelta(days=29)
    previous_start = as_of - timedelta(days=59)
    previous_end = recent_start - timedelta(days=1)
    recent = [tx for tx in valid if (_date(tx) or date.min) >= recent_start]
    previous = [
        tx for tx in valid if previous_start <= (_date(tx) or date.min) <= previous_end
    ]
    recent_median = _median(tx.price_10k_krw for tx in recent)
    previous_median = _median(tx.price_10k_krw for tx in previous)
    if previous:
        volume_change: float | str | None = round((len(recent) - len(previous)) / len(previous) * 100, 2)
        state = "COMPARABLE"
    elif recent:
        volume_change = None
        state = "REOPENED"
    else:
        volume_change = None
        state = "NO_BASELINE"
    price_change = (
        round((recent_median - previous_median) / previous_median * 100, 2)
        if recent_median is not None and previous_median not in {None, 0}
        else None
    )
    return {
        "as_of": as_of.isoformat(),
        "recent_30d_count": len(recent),
        "previous_30d_count": len(previous),
        "volume_change_pct": volume_change,
        "comparison_state": state,
        "recent_30d_median_price_10k_krw": recent_median,
        "previous_30d_median_price_10k_krw": previous_median,
        "median_price_change_pct": price_change,
        "quality": quality_grade(len(recent)),
    }


def group_by_complex(transactions: list[Transaction]) -> dict[str, list[Transaction]]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    display_names: dict[str, str] = {}
    for tx in transactions:
        if not tx.complex_name:
            continue
        key = normalize_name(tx.complex_name)
        groups[key].append(tx)
        display_names.setdefault(key, tx.complex_name)
    return {display_names[key]: value for key, value in groups.items()}


def detect_signals(sales: list[Transaction], *, resumed_days: int = 90) -> list[dict[str, Any]]:
    grouped = group_by_complex(
        [tx for tx in sales if not tx.is_canceled and tx.price_10k_krw is not None]
    )
    signals: list[dict[str, Any]] = []
    for complex_name, rows in grouped.items():
        rows.sort(key=lambda tx: (tx.contract_date or "", tx.source_record_id))
        peak: int | None = None
        previous_date: date | None = None
        for tx in rows:
            tx_date = _date(tx)
            price = tx.price_10k_krw
            if price is None:
                continue
            if peak is not None and price > peak:
                signals.append(
                    {
                        "type": "NEW_HIGH",
                        "complex_name": complex_name,
                        "contract_date": tx.contract_date,
                        "price_10k_krw": price,
                        "previous_peak_10k_krw": peak,
                        "source_record_id": tx.source_record_id,
                    }
                )
            if tx_date is not None and previous_date is not None:
                gap = (tx_date - previous_date).days
                if gap >= resumed_days:
                    signals.append(
                        {
                            "type": "TRANSACTION_RESUMED",
                            "complex_name": complex_name,
                            "contract_date": tx.contract_date,
                            "gap_days": gap,
                            "source_record_id": tx.source_record_id,
                        }
                    )
            peak = max(peak or price, price)
            if tx_date is not None:
                previous_date = tx_date
    signals.sort(key=lambda item: (item.get("contract_date") or "", item["type"]), reverse=True)
    return signals


def rank_complexes(
    sales: list[Transaction],
    rents: list[Transaction],
    *,
    metric: str,
    limit: int = 20,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    sale_groups = group_by_complex(sales)
    rent_groups = group_by_complex(rents)
    rent_index = {normalize_name(name): rows for name, rows in rent_groups.items()}
    rows: list[dict[str, Any]] = []
    for name, group in sale_groups.items():
        snapshot = build_snapshot(group, rent_index.get(normalize_name(name), []), as_of=as_of)
        mapping = {
            "transaction_volume": snapshot["sale_sample_count"],
            "median_price": snapshot["median_sale_price_10k_krw"],
            "recovery_rate": snapshot["recovery_rate_pct"],
            "volume_momentum": (
                snapshot["volume_momentum"]
                if isinstance(snapshot["volume_momentum"], (int, float))
                else None
            ),
            "jeonse_ratio": snapshot["jeonse_ratio_pct"],
            "estimated_gap": snapshot["estimated_gap_10k_krw"],
        }
        value = mapping.get(metric)
        if value is not None:
            rows.append({"complex_name": name, "metric": metric, "value": value, **snapshot})
    rows.sort(key=lambda row: float(row["value"]), reverse=True)
    for index, row in enumerate(rows[:limit], start=1):
        row["rank"] = index
    return rows[:limit]
