"""Public-data-backed apartment candidate generation and recommendation."""

from __future__ import annotations

import asyncio
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from kr_apartment_market.config import Settings
from kr_apartment_market.data.public_data import PublicDataClient
from kr_apartment_market.data.regions import resolve_region
from kr_apartment_market.home.listing_links import build_listing_links
from kr_apartment_market.home.models import CandidateFacts
from kr_apartment_market.home.scoring import score_candidate
from kr_apartment_market.models import Transaction
from kr_apartment_market.services.metrics import build_snapshot
from kr_apartment_market.utils import normalize_name


def _median(values: list[float | int | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return float(statistics.median(clean)) if clean else None


def _region_name(code: str, profile: dict[str, Any]) -> str:
    configured = profile.get("region_names", {}).get(code)
    if configured:
        return str(configured)
    result = resolve_region(code, limit=1)
    matches = result.get("matches", [])
    return str(matches[0]["name"]) if matches else code


def _group(rows: list[Transaction]) -> dict[str, tuple[str, list[Transaction]]]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    names: dict[str, str] = {}
    for row in rows:
        if not row.complex_name:
            continue
        key = normalize_name(row.complex_name)
        if not key:
            continue
        names.setdefault(key, row.complex_name)
        groups[key].append(row)
    return {key: (names[key], value) for key, value in groups.items()}


def _enrichment_index(enrichments: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in enrichments or []:
        if not isinstance(item, dict):
            continue
        name = normalize_name(str(item.get("complex_name", "")))
        if not name:
            continue
        code = str(item.get("lawd_code", "")).strip()
        payload = {
            key: value
            for key, value in item.items()
            if key not in {"lawd_code", "complex_name"}
        }
        index[name] = payload
        if code:
            index[f"{code}|{name}"] = payload
    return index


def _primary_rows(
    transaction_type: str,
    sales: list[Transaction],
    rents: list[Transaction],
) -> list[Transaction]:
    if transaction_type == "sale":
        return [row for row in sales if row.price_10k_krw is not None and not row.is_canceled]
    if transaction_type == "jeonse":
        return [
            row
            for row in rents
            if row.deposit_10k_krw is not None
            and (row.monthly_rent_10k_krw or 0) == 0
            and not row.is_canceled
        ]
    return [
        row
        for row in rents
        if row.deposit_10k_krw is not None
        and (row.monthly_rent_10k_krw or 0) > 0
        and not row.is_canceled
    ]


def build_candidate_facts(
    *,
    profile: dict[str, Any],
    lawd_code: str,
    region_name: str,
    sales: list[Transaction],
    rents: list[Transaction],
    source_months: list[str],
    enrichments: list[dict[str, Any]] | None = None,
    as_of: date | None = None,
) -> list[CandidateFacts]:
    """Build candidate facts from already normalized transactions."""

    as_of = as_of or date.today()
    sale_groups = _group(sales)
    rent_groups = _group(rents)
    primary_groups = sale_groups if profile["transaction_type"] == "sale" else rent_groups
    enrichment_map = _enrichment_index(enrichments)
    candidates: list[CandidateFacts] = []

    for key, (display_name, primary_unfiltered) in primary_groups.items():
        sale_rows = sale_groups.get(key, (display_name, []))[1]
        rent_rows = rent_groups.get(key, (display_name, []))[1]
        primary = _primary_rows(profile["transaction_type"], sale_rows, rent_rows)
        if not primary:
            continue
        snapshot = build_snapshot(sale_rows, rent_rows, as_of=as_of)
        primary.sort(key=lambda row: (row.contract_date or "", row.source_record_id), reverse=True)

        monthly_rows = [
            row
            for row in rent_rows
            if not row.is_canceled and (row.monthly_rent_10k_krw or 0) > 0
        ]
        if profile["transaction_type"] == "sale":
            reference = snapshot["median_sale_price_10k_krw"]
        elif profile["transaction_type"] == "jeonse":
            reference = snapshot["median_jeonse_deposit_10k_krw"]
        else:
            reference = _median([row.monthly_rent_10k_krw for row in monthly_rows])

        areas = [float(row.area_m2) for row in primary if row.area_m2 is not None]
        years = [int(row.build_year) for row in primary if row.build_year]
        enrichment = enrichment_map.get(f"{lawd_code}|{key}") or enrichment_map.get(key) or {}

        candidates.append(
            CandidateFacts(
                lawd_code=lawd_code,
                region_name=region_name,
                complex_name=display_name,
                transaction_type=profile["transaction_type"],
                reference_price_10k_krw=reference,
                median_sale_price_10k_krw=snapshot["median_sale_price_10k_krw"],
                median_jeonse_deposit_10k_krw=snapshot[
                    "median_jeonse_deposit_10k_krw"
                ],
                median_monthly_deposit_10k_krw=_median(
                    [row.deposit_10k_krw for row in monthly_rows]
                ),
                median_monthly_rent_10k_krw=_median(
                    [row.monthly_rent_10k_krw for row in monthly_rows]
                ),
                latest_contract_date=primary[0].contract_date,
                transaction_count=len(primary),
                area_min_m2=min(areas) if areas else None,
                area_max_m2=max(areas) if areas else None,
                area_median_m2=_median(areas),
                representative_build_year=(
                    int(round(statistics.median(years))) if years else None
                ),
                recovery_rate_pct=snapshot["recovery_rate_pct"],
                jeonse_ratio_pct=snapshot["jeonse_ratio_pct"],
                estimated_gap_10k_krw=snapshot["estimated_gap_10k_krw"],
                source_months=sorted(set(source_months)),
                enrichment=dict(enrichment),
            )
        )
    return candidates


def _diversify(candidates: list[dict[str, Any]], mode: str, limit: int) -> list[dict[str, Any]]:
    if mode == "none":
        return candidates[:limit]
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    region_order: list[str] = []
    for candidate in candidates:
        code = str(candidate["lawd_code"])
        if code not in buckets:
            region_order.append(code)
        buckets[code].append(candidate)
    result: list[dict[str, Any]] = []
    while len(result) < limit:
        added = False
        for code in region_order:
            if buckets[code]:
                result.append(buckets[code].pop(0))
                added = True
                if len(result) >= limit:
                    break
        if not added:
            break
    return result


def rank_candidate_facts(
    *,
    profile: dict[str, Any],
    facts: list[CandidateFacts],
    as_of: date | None = None,
    include_excluded: bool = False,
    include_listing_links: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Score and rank candidate facts without network access."""

    as_of = as_of or date.today()
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate_facts in facts:
        score = score_candidate(profile, candidate_facts, as_of=as_of)
        row = {
            "lawd_code": candidate_facts.lawd_code,
            "region_name": candidate_facts.region_name,
            "complex_name": candidate_facts.complex_name,
            "transaction_type": candidate_facts.transaction_type,
            "facts": candidate_facts.to_dict(),
            "score": score.to_dict(),
            "listing_links": (
                build_listing_links(
                    region_name=candidate_facts.region_name,
                    complex_name=candidate_facts.complex_name,
                    transaction_type=candidate_facts.transaction_type,
                    area_m2=candidate_facts.area_median_m2,
                    sources=profile.get("listing_sources"),
                )
                if include_listing_links
                else []
            ),
        }
        if score.excluded:
            excluded.append(row)
        else:
            rows.append(row)

    rows.sort(
        key=lambda item: (
            -float(item["score"]["match_score"]),
            -float(item["score"]["confidence_score"]),
            -int(item["facts"]["transaction_count"]),
            item["complex_name"],
        )
    )
    excluded.sort(
        key=lambda item: (
            len(item["score"]["exclusion_reasons"]),
            -float(item["score"]["match_score"]),
            item["complex_name"],
        )
    )
    effective_limit = min(limit or profile["candidate_limit"], 100)
    selected = _diversify(rows, profile.get("diversity_mode", "region"), effective_limit)
    for index, item in enumerate(selected, start=1):
        item["rank"] = index
    if include_excluded:
        for index, item in enumerate(excluded[:effective_limit], start=1):
            item["excluded_rank"] = index
    return {
        "profile_id": profile["profile_id"],
        "as_of": as_of.isoformat(),
        "candidate_count_before_constraints": len(rows) + len(excluded),
        "eligible_candidate_count": len(rows),
        "excluded_candidate_count": len(excluded),
        "returned_count": len(selected),
        "candidates": selected,
        "excluded_candidates": excluded[:effective_limit] if include_excluded else [],
    }


async def recommend_complexes(
    *,
    profile: dict[str, Any],
    settings: Settings,
    date_from: str | None = None,
    date_to: str | None = None,
    enrichments: list[dict[str, Any]] | None = None,
    include_excluded: bool = False,
    include_listing_links: bool = True,
    limit: int | None = None,
    client: PublicDataClient | None = None,
) -> dict[str, Any]:
    """Fetch public data for profile regions and return ranked candidates."""

    as_of = date.today()
    if date_to:
        try:
            as_of = min(date.fromisoformat(date_to), date.today())
        except ValueError:
            pass
    date_to = date_to or as_of.isoformat()
    date_from = date_from or (as_of - timedelta(days=365)).isoformat()
    public_client = client or PublicDataClient(settings)
    semaphore = asyncio.Semaphore(4)

    area = profile["area"]
    query_kwargs: dict[str, Any] = {
        "date_from": date_from,
        "date_to": date_to,
        "include_canceled": False,
    }
    if area.get("target_m2") is not None:
        query_kwargs["area_m2"] = area["target_m2"]
        query_kwargs["area_tolerance_m2"] = area.get("tolerance_m2", 1.0)
    else:
        query_kwargs["area_min_m2"] = area.get("min_m2")
        query_kwargs["area_max_m2"] = area.get("max_m2")

    async def fetch_region(code: str) -> tuple[str, list[Transaction], list[Transaction], list[str]]:
        async with semaphore:
            sales, rents = await asyncio.gather(
                public_client.fetch_transactions(
                    property_type="apartment",
                    trade_type="sale",
                    lawd_code=code,
                    **query_kwargs,
                ),
                public_client.fetch_transactions(
                    property_type="apartment",
                    trade_type="rent",
                    lawd_code=code,
                    **query_kwargs,
                ),
            )
        months = sorted(set(sales.deal_months + rents.deal_months))
        return code, sales.transactions, rents.transactions, months

    fetched = await asyncio.gather(*(fetch_region(code) for code in profile["lawd_codes"]))
    all_facts: list[CandidateFacts] = []
    source_months: dict[str, list[str]] = {}
    for code, sales, rents, months in fetched:
        source_months[code] = months
        all_facts.extend(
            build_candidate_facts(
                profile=profile,
                lawd_code=code,
                region_name=_region_name(code, profile),
                sales=sales,
                rents=rents,
                source_months=months,
                enrichments=enrichments,
                as_of=as_of,
            )
        )
    result = rank_candidate_facts(
        profile=profile,
        facts=all_facts,
        as_of=as_of,
        include_excluded=include_excluded,
        include_listing_links=include_listing_links,
        limit=limit,
    )
    result.update(
        {
            "date_from": date_from,
            "date_to": date_to,
            "lawd_codes": profile["lawd_codes"],
            "source_months": source_months,
        }
    )
    return result
