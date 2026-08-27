"""MCP tools for the platform-neutral AI Home Finder."""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from typing import Any

from kr_apartment_market.config import Settings
from kr_apartment_market.home.listing_links import (
    build_listing_links,
    get_source_capabilities,
    inspect_listing_url,
    load_listing_registry,
)
from kr_apartment_market.home.models import CandidateFacts, validate_search_profile
from kr_apartment_market.home.recommender import rank_candidate_facts, recommend_complexes
from kr_apartment_market.home.scoring import score_candidate
from kr_apartment_market.home.storage import HomeFinderStore
from kr_apartment_market.mcp_compat import FastMCP
from kr_apartment_market.tools.canonical import _envelope, _error_envelope

_HOME_NOTICE = (
    "추천은 입력 조건과 최신 신고·공개 실거래를 이용한 설명 가능한 적합도 분석이며, "
    "미래 가격·매수 적정성·매물 존재를 보장하지 않습니다."
)
_LISTING_NOTICE = (
    "광고매물 링크는 LINK_OUT_ONLY입니다. 가격·상태·연락처는 각 원문 플랫폼에서 확인하세요."
)


def _store(settings: Settings) -> HomeFinderStore:
    return HomeFinderStore(settings.home_finder_path, settings.timezone)


def _profile(
    settings: Settings,
    *,
    profile_id: str | None,
    inline_profile: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    if inline_profile is not None:
        return validate_search_profile(inline_profile, timezone=settings.timezone)
    if not profile_id:
        raise ValueError("profile_id or inline_profile is required")
    stored = _store(settings).get_profile(profile_id)
    if stored is None:
        raise ValueError(f"profile not found: {profile_id}")
    return stored, []


def _candidate_facts(payload: dict[str, Any]) -> CandidateFacts:
    if not isinstance(payload, dict):
        raise ValueError("candidate_facts must be an object")
    allowed = {item.name for item in fields(CandidateFacts)}
    data = {key: value for key, value in payload.items() if key in allowed}
    required = {"lawd_code", "complex_name", "transaction_type", "reference_price_10k_krw"}
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"candidate_facts missing required fields: {', '.join(missing)}")
    data.setdefault("region_name", None)
    return CandidateFacts(**data)


def register_home_tools(mcp: FastMCP, settings: Settings) -> list[str]:
    """Register v3 Home Finder tools and return their names."""

    registered: list[str] = []

    def tool(name: str):
        def decorator(func):
            registered.append(name)
            return mcp.tool(name=name)(func)

        return decorator

    @tool("kr_home.validate_search_profile")
    def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
        """Normalize a housing-preference profile without saving it."""
        try:
            normalized, warnings = validate_search_profile(profile, timezone=settings.timezone)
            return _envelope(
                {"profile": normalized, "warnings": warnings},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.create_search_profile")
    def create_search_profile(profile: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist a new Home Finder profile."""
        try:
            normalized, warnings = validate_search_profile(profile, timezone=settings.timezone)
            saved = _store(settings).create_profile(normalized)
            return _envelope(
                {"profile": saved, "warnings": warnings},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.get_search_profile")
    def get_search_profile(profile_id: str | None = None) -> dict[str, Any]:
        """Get one profile or list all locally stored profiles."""
        try:
            store = _store(settings)
            if profile_id:
                profile = store.get_profile(profile_id)
                if profile is None:
                    raise ValueError(f"profile not found: {profile_id}")
                data: Any = {"profile": profile}
            else:
                data = {"profiles": store.list_profiles()}
            return _envelope(data, settings, notices=[_HOME_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.update_search_profile")
    def update_search_profile(profile_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Patch, revalidate, and persist a profile."""
        try:
            store = _store(settings)
            existing = store.get_profile(profile_id)
            if existing is None:
                raise ValueError(f"profile not found: {profile_id}")
            patch = dict(patch)
            patch["profile_id"] = profile_id
            normalized, warnings = validate_search_profile(
                patch, timezone=settings.timezone, existing=existing
            )
            saved = store.put_profile(normalized)
            return _envelope(
                {"profile": saved, "warnings": warnings},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.delete_search_profile")
    def delete_search_profile(profile_id: str) -> dict[str, Any]:
        """Delete a profile and its dependent saved searches."""
        try:
            deleted = _store(settings).delete_profile(profile_id)
            return _envelope(
                {"profile_id": profile_id, "deleted": deleted},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.recommend_complexes")
    async def recommend_complexes_tool(
        profile_id: str | None = None,
        inline_profile: dict[str, Any] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        enrichments: list[dict[str, Any]] | None = None,
        include_excluded: bool = False,
        include_listing_links: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Recommend apartment complexes from MOLIT data using an explainable profile."""
        try:
            profile, warnings = _profile(
                settings, profile_id=profile_id, inline_profile=inline_profile
            )
            result = await recommend_complexes(
                profile=profile,
                settings=settings,
                date_from=date_from,
                date_to=date_to,
                enrichments=enrichments,
                include_excluded=include_excluded,
                include_listing_links=include_listing_links,
                limit=limit,
            )
            sources = [
                {
                    "source": "국토교통부 실거래가 공개 API",
                    "provider": "국토교통부/공공데이터포털",
                    "lawd_code": code,
                    "deal_months": months,
                    "access": "API",
                }
                for code, months in result.get("source_months", {}).items()
            ]
            return _envelope(
                {"profile": profile, "profile_warnings": warnings, **result},
                settings,
                sources=sources,
                notices=[_HOME_NOTICE, _LISTING_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.explain_complex_match")
    def explain_complex_match(
        candidate_facts: dict[str, Any],
        profile_id: str | None = None,
        inline_profile: dict[str, Any] | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Score and explain one precomputed candidate without network access."""
        try:
            profile, warnings = _profile(
                settings, profile_id=profile_id, inline_profile=inline_profile
            )
            facts = _candidate_facts(candidate_facts)
            score = score_candidate(
                profile, facts, as_of=date.fromisoformat(as_of) if as_of else None
            )
            return _envelope(
                {
                    "profile_id": profile["profile_id"],
                    "profile_warnings": warnings,
                    "facts": facts.to_dict(),
                    "score": score.to_dict(),
                },
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.compare_candidates")
    def compare_candidates(
        candidates: list[dict[str, Any]],
        profile_id: str | None = None,
        inline_profile: dict[str, Any] | None = None,
        include_excluded: bool = True,
        include_listing_links: bool = True,
        limit: int | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Apply the same profile and scoring model to precomputed candidates."""
        try:
            if not 1 <= len(candidates) <= 100:
                raise ValueError("candidates must contain 1 to 100 items")
            profile, warnings = _profile(
                settings, profile_id=profile_id, inline_profile=inline_profile
            )
            result = rank_candidate_facts(
                profile=profile,
                facts=[_candidate_facts(item) for item in candidates],
                as_of=date.fromisoformat(as_of) if as_of else None,
                include_excluded=include_excluded,
                include_listing_links=include_listing_links,
                limit=limit,
            )
            return _envelope(
                {"profile": profile, "profile_warnings": warnings, **result},
                settings,
                notices=[_HOME_NOTICE, _LISTING_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.find_listing_links")
    def find_listing_links(
        region_name: str | None = None,
        complex_name: str | None = None,
        transaction_type: str = "sale",
        area_m2: float | None = None,
        sources: list[str] | None = None,
        property_type: str = "apartment",
    ) -> dict[str, Any]:
        """Build policy-gated original-platform listing discovery links."""
        try:
            if not region_name and not complex_name:
                raise ValueError("region_name or complex_name is required")
            links = build_listing_links(
                region_name=region_name,
                complex_name=complex_name,
                transaction_type=transaction_type,
                area_m2=area_m2,
                sources=sources,
                property_type=property_type,
            )
            return _envelope(
                {"links": links, "count": len(links)},
                settings,
                notices=[_LISTING_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.get_listing_source_capabilities")
    def get_listing_source_capabilities(source_id: str | None = None) -> dict[str, Any]:
        """Return allowed operations and data-handling policy for listing sources."""
        try:
            registry = load_listing_registry()
            rows = get_source_capabilities(source_id)
            return _envelope(
                {
                    "registry_version": registry["registryVersion"],
                    "reviewed_at": registry["reviewedAt"],
                    "sources": rows,
                },
                settings,
                notices=[_LISTING_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.inspect_listing_url")
    def inspect_listing_url_tool(url: str) -> dict[str, Any]:
        """Classify a user-supplied listing URL without fetching its page."""
        try:
            return _envelope(
                inspect_listing_url(url), settings, notices=[_LISTING_NOTICE]
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.save_search")
    def save_search(
        profile_id: str,
        label: str | None = None,
        search_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        candidate_limit: int | None = None,
    ) -> dict[str, Any]:
        """Save a reusable recommendation query."""
        try:
            saved = _store(settings).save_search(
                profile_id=profile_id,
                label=label,
                search_id=search_id,
                date_from=date_from,
                date_to=date_to,
                candidate_limit=candidate_limit,
            )
            return _envelope({"saved_search": saved}, settings, notices=[_HOME_NOTICE])
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.get_saved_searches")
    def get_saved_searches(profile_id: str | None = None) -> dict[str, Any]:
        """List saved Home Finder searches."""
        try:
            rows = _store(settings).list_saved_searches(profile_id)
            return _envelope(
                {"saved_searches": rows, "count": len(rows)},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.delete_saved_search")
    def delete_saved_search(search_id: str) -> dict[str, Any]:
        """Delete a saved search and its previous run snapshot."""
        try:
            deleted = _store(settings).delete_saved_search(search_id)
            return _envelope(
                {"search_id": search_id, "deleted": deleted},
                settings,
                notices=[_HOME_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    @tool("kr_home.get_search_updates")
    async def get_search_updates(
        search_id: str,
        enrichments: list[dict[str, Any]] | None = None,
        include_listing_links: bool = True,
    ) -> dict[str, Any]:
        """Rerun a saved search and report candidate/rank/reference-price changes."""
        try:
            store = _store(settings)
            saved = store.get_saved_search(search_id)
            if saved is None:
                raise ValueError(f"saved search not found: {search_id}")
            profile = store.get_profile(str(saved["profile_id"]))
            if profile is None:
                raise ValueError(f"profile not found: {saved['profile_id']}")
            previous = store.get_last_run(search_id)
            result = await recommend_complexes(
                profile=profile,
                settings=settings,
                date_from=saved.get("date_from"),
                date_to=saved.get("date_to"),
                enrichments=enrichments,
                include_excluded=False,
                include_listing_links=include_listing_links,
                limit=saved.get("candidate_limit"),
            )
            events = store.diff_runs(previous, result["candidates"])
            run = store.record_run(
                search_id=search_id,
                candidates=result["candidates"],
                query_context={
                    "date_from": result["date_from"],
                    "date_to": result["date_to"],
                },
            )
            return _envelope(
                {
                    "saved_search": saved,
                    "first_run": previous is None,
                    "baseline_status": (
                        "NO_BASELINE" if previous is None else "NO_CHANGE" if not events else "CHANGED"
                    ),
                    "event_count": len(events),
                    "events": events,
                    "current": result,
                    "recorded_run": {
                        "run_id": run["run_id"],
                        "ran_at": run["ran_at"],
                    },
                },
                settings,
                notices=[_HOME_NOTICE, _LISTING_NOTICE],
            )
        except Exception as exc:
            return _error_envelope(exc, settings)

    return registered
