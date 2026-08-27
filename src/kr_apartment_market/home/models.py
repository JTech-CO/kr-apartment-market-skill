"""Home Finder profile and candidate models.

The module intentionally uses dataclasses and explicit validation instead of a
large validation dependency.  MCP clients can submit plain JSON objects and
receive a normalized, versioned profile that the deterministic scoring engine
can reproduce.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

HomeTransactionType = Literal["sale", "jeonse", "monthly_rent"]
UnknownPolicy = Literal["neutral", "penalize", "exclude"]
DiversityMode = Literal["none", "region"]

DEFAULT_LISTING_SOURCES = ["naver", "daangn", "peterpan", "asil", "kb"]
SUPPORTED_LISTING_SOURCES = {
    "naver",
    "daangn",
    "peterpan",
    "asil",
    "kb",
    "dabang",
    "zigbang",
    "disco",
    "valuemap",
    "ddangya",
    "onbid",
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "affordability": 0.25,
    "area_fit": 0.15,
    "building_age": 0.08,
    "liquidity": 0.12,
    "recency": 0.10,
    "recovery": 0.07,
    "jeonse_safety": 0.05,
    "commute": 0.08,
    "education": 0.04,
    "parking": 0.03,
    "listing_availability": 0.03,
}


@dataclass(slots=True)
class CandidateFacts:
    """Facts used by the scoring engine for one apartment complex."""

    lawd_code: str
    region_name: str | None
    complex_name: str
    transaction_type: HomeTransactionType
    reference_price_10k_krw: float | None
    median_sale_price_10k_krw: float | None = None
    median_jeonse_deposit_10k_krw: float | None = None
    median_monthly_deposit_10k_krw: float | None = None
    median_monthly_rent_10k_krw: float | None = None
    latest_contract_date: str | None = None
    transaction_count: int = 0
    area_min_m2: float | None = None
    area_max_m2: float | None = None
    area_median_m2: float | None = None
    representative_build_year: int | None = None
    recovery_rate_pct: float | None = None
    jeonse_ratio_pct: float | None = None
    estimated_gap_10k_krw: float | None = None
    source_months: list[str] = field(default_factory=list)
    enrichment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreComponent:
    name: str
    score: float | None
    weight: float
    available: bool
    source: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CandidateScore:
    match_score: float
    confidence_score: float
    excluded: bool
    exclusion_reasons: list[str]
    components: list[ScoreComponent]
    strengths: list[str]
    tradeoffs: list[str]
    unknowns: list[str]
    available_weight: float
    total_weight: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["components"] = [item.to_dict() for item in self.components]
        return data


def _now(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


def _number(value: Any, *, name: str, minimum: float | None = None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _integer(value: Any, *, name: str, minimum: int | None = None) -> int | None:
    number = _number(value, name=name, minimum=minimum)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"{name} must be an integer")
    return int(number)


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("boolean field must be true or false")


def _lawd_codes(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError("lawd_codes must be a string or array")
    result: list[str] = []
    for item in values:
        code = str(item).strip()
        if len(code) != 5 or not code.isdigit():
            raise ValueError(f"invalid 5-digit lawd_code: {code}")
        if code not in result:
            result.append(code)
    if not result:
        raise ValueError("lawd_codes must contain at least one region")
    if len(result) > 20:
        raise ValueError("lawd_codes may contain at most 20 regions")
    return result


def _normalize_weights(value: Any) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    if value is not None:
        if not isinstance(value, dict):
            raise ValueError("weights must be an object")
        unknown = sorted(set(value) - set(DEFAULT_WEIGHTS))
        if unknown:
            raise ValueError(f"unsupported weight names: {', '.join(unknown)}")
        for key, raw in value.items():
            parsed = _number(raw, name=f"weights.{key}", minimum=0)
            assert parsed is not None
            weights[key] = parsed
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("at least one scoring weight must be greater than zero")
    return {key: round(value / total, 8) for key, value in weights.items()}


def validate_search_profile(
    payload: dict[str, Any],
    *,
    timezone: str = "Asia/Seoul",
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize a Home Finder profile.

    ``existing`` enables patch-style updates while still producing a complete
    versioned profile.  The function does not perform network calls.
    """

    if not isinstance(payload, dict):
        raise ValueError("profile must be an object")
    merged = dict(existing or {})
    for key, value in payload.items():
        if key not in {"created_at", "updated_at", "schema_version"}:
            merged[key] = value

    transaction_type = str(merged.get("transaction_type", "sale")).strip().casefold()
    if transaction_type not in {"sale", "jeonse", "monthly_rent"}:
        raise ValueError("transaction_type must be sale, jeonse, or monthly_rent")

    property_types_raw = merged.get("property_types", ["apartment"])
    if isinstance(property_types_raw, str):
        property_types_raw = [property_types_raw]
    if not isinstance(property_types_raw, list) or not property_types_raw:
        raise ValueError("property_types must be a non-empty array")
    property_types = []
    for raw in property_types_raw:
        value = str(raw).strip().casefold()
        if value != "apartment":
            raise ValueError("v3 recommendation currently supports property_types=['apartment']")
        if value not in property_types:
            property_types.append(value)

    budget_raw = merged.get("budget", {}) or {}
    if not isinstance(budget_raw, dict):
        raise ValueError("budget must be an object")
    budget = {
        "min_price_10k_krw": _number(
            budget_raw.get("min_price_10k_krw"), name="budget.min_price_10k_krw", minimum=0
        ),
        "max_price_10k_krw": _number(
            budget_raw.get("max_price_10k_krw"), name="budget.max_price_10k_krw", minimum=0
        ),
        "max_deposit_10k_krw": _number(
            budget_raw.get("max_deposit_10k_krw"),
            name="budget.max_deposit_10k_krw",
            minimum=0,
        ),
        "max_monthly_rent_10k_krw": _number(
            budget_raw.get("max_monthly_rent_10k_krw"),
            name="budget.max_monthly_rent_10k_krw",
            minimum=0,
        ),
    }
    if (
        budget["min_price_10k_krw"] is not None
        and budget["max_price_10k_krw"] is not None
        and budget["min_price_10k_krw"] > budget["max_price_10k_krw"]
    ):
        raise ValueError("budget.min_price_10k_krw must not exceed max_price_10k_krw")

    area_raw = merged.get("area", {}) or {}
    if not isinstance(area_raw, dict):
        raise ValueError("area must be an object")
    area = {
        "min_m2": _number(area_raw.get("min_m2"), name="area.min_m2", minimum=0),
        "max_m2": _number(area_raw.get("max_m2"), name="area.max_m2", minimum=0),
        "target_m2": _number(area_raw.get("target_m2"), name="area.target_m2", minimum=0),
        "tolerance_m2": _number(
            area_raw.get("tolerance_m2", 1.0), name="area.tolerance_m2", minimum=0
        ),
    }
    if area["min_m2"] is not None and area["max_m2"] is not None and area["min_m2"] > area["max_m2"]:
        raise ValueError("area.min_m2 must not exceed area.max_m2")

    building_raw = merged.get("building", {}) or {}
    if not isinstance(building_raw, dict):
        raise ValueError("building must be an object")
    building = {
        "max_age_years": _integer(
            building_raw.get("max_age_years"), name="building.max_age_years", minimum=0
        ),
        "min_households": _integer(
            building_raw.get("min_households"), name="building.min_households", minimum=0
        ),
        "min_parking_per_household": _number(
            building_raw.get("min_parking_per_household"),
            name="building.min_parking_per_household",
            minimum=0,
        ),
        "elevator_required": _bool(building_raw.get("elevator_required"), default=False),
    }

    household = merged.get("household", {}) or {}
    if not isinstance(household, dict):
        raise ValueError("household must be an object")
    household = {
        "adults": _integer(household.get("adults", 1), name="household.adults", minimum=0),
        "children": _integer(
            household.get("children", 0), name="household.children", minimum=0
        ),
        "cars": _integer(household.get("cars", 0), name="household.cars", minimum=0),
        "pets": [str(item).strip() for item in household.get("pets", []) if str(item).strip()],
    }

    commute_raw = merged.get("commute", []) or []
    if not isinstance(commute_raw, list):
        raise ValueError("commute must be an array")
    commute = []
    for index, destination in enumerate(commute_raw):
        if not isinstance(destination, dict):
            raise ValueError(f"commute[{index}] must be an object")
        name = str(destination.get("name", "")).strip()
        if not name:
            raise ValueError(f"commute[{index}].name is required")
        commute.append(
            {
                "name": name,
                "max_minutes": _integer(
                    destination.get("max_minutes"),
                    name=f"commute[{index}].max_minutes",
                    minimum=1,
                ),
                "weight": _number(
                    destination.get("weight", 1),
                    name=f"commute[{index}].weight",
                    minimum=0,
                ),
            }
        )

    unknown_policy = str(merged.get("unknown_policy", "neutral")).strip().casefold()
    if unknown_policy not in {"neutral", "penalize", "exclude"}:
        raise ValueError("unknown_policy must be neutral, penalize, or exclude")

    hard_raw = merged.get("hard_constraints", {}) or {}
    if not isinstance(hard_raw, dict):
        raise ValueError("hard_constraints must be an object")
    hard_constraints = {
        "budget": _bool(hard_raw.get("budget"), default=True),
        "area": _bool(hard_raw.get("area"), default=True),
        "building_age": _bool(hard_raw.get("building_age"), default=False),
        "minimum_transactions": _bool(
            hard_raw.get("minimum_transactions"), default=True
        ),
        "parking": _bool(hard_raw.get("parking"), default=False),
        "commute": _bool(hard_raw.get("commute"), default=False),
    }

    listing_sources_raw = merged.get("listing_sources", DEFAULT_LISTING_SOURCES)
    if isinstance(listing_sources_raw, str):
        listing_sources_raw = [listing_sources_raw]
    if not isinstance(listing_sources_raw, list):
        raise ValueError("listing_sources must be an array")
    listing_sources: list[str] = []
    for raw in listing_sources_raw:
        source = str(raw).strip().casefold()
        if source not in SUPPORTED_LISTING_SOURCES:
            raise ValueError(f"unsupported listing source: {source}")
        if source not in listing_sources:
            listing_sources.append(source)

    profile_id = str(merged.get("profile_id") or uuid.uuid4()).strip()
    if not profile_id:
        raise ValueError("profile_id must not be empty")
    name = str(merged.get("name") or "주택 탐색 프로필").strip()
    if not name:
        raise ValueError("name must not be empty")

    minimum_transactions = _integer(
        merged.get("minimum_transactions", 1), name="minimum_transactions", minimum=0
    )
    candidate_limit = _integer(
        merged.get("candidate_limit", 20), name="candidate_limit", minimum=1
    )
    assert minimum_transactions is not None and candidate_limit is not None
    if candidate_limit > 100:
        raise ValueError("candidate_limit must be <= 100")

    diversity_mode = str(merged.get("diversity_mode", "region")).strip().casefold()
    if diversity_mode not in {"none", "region"}:
        raise ValueError("diversity_mode must be none or region")

    preferences = merged.get("preferences", {}) or {}
    if not isinstance(preferences, dict):
        raise ValueError("preferences must be an object")

    now = _now(timezone)
    normalized = {
        "schema_version": "3.0.0",
        "profile_id": profile_id,
        "name": name,
        "transaction_type": transaction_type,
        "property_types": property_types,
        "lawd_codes": _lawd_codes(merged.get("lawd_codes")),
        "region_names": {
            str(key): str(value).strip()
            for key, value in (merged.get("region_names", {}) or {}).items()
            if str(key).strip() and str(value).strip()
        },
        "budget": budget,
        "area": area,
        "building": building,
        "household": household,
        "commute": commute,
        "preferences": preferences,
        "hard_constraints": hard_constraints,
        "weights": _normalize_weights(merged.get("weights")),
        "unknown_policy": unknown_policy,
        "minimum_transactions": minimum_transactions,
        "candidate_limit": candidate_limit,
        "diversity_mode": diversity_mode,
        "listing_sources": listing_sources,
        "created_at": (existing or {}).get("created_at", now),
        "updated_at": now,
    }

    warnings: list[str] = []
    if transaction_type == "sale" and budget["max_price_10k_krw"] is None:
        warnings.append("매매 최대 예산이 없어 가격 필터가 약하게 적용됩니다.")
    if transaction_type == "jeonse" and budget["max_deposit_10k_krw"] is None:
        warnings.append("전세 최대 보증금이 없어 가격 필터가 약하게 적용됩니다.")
    if transaction_type == "monthly_rent" and (
        budget["max_deposit_10k_krw"] is None
        or budget["max_monthly_rent_10k_krw"] is None
    ):
        warnings.append("월세 보증금·월세 상한 중 일부가 없어 가격 필터가 약하게 적용됩니다.")
    if not commute:
        warnings.append("통근 목적지가 없어 통근 점수는 데이터 없음으로 처리됩니다.")
    if building["min_parking_per_household"] is not None:
        warnings.append("주차 데이터는 공공 실거래 API에 없어 별도 enrichment가 필요합니다.")
    if building["min_households"] is not None:
        warnings.append("세대수 데이터는 공공 실거래 API에 없어 별도 enrichment가 필요합니다.")
    if candidate_limit > 50:
        warnings.append("후보 수가 많아 여러 지역 조회 시 공공 API 호출량이 커질 수 있습니다.")
    return normalized, warnings
