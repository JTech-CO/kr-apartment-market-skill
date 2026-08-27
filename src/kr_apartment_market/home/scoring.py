"""Deterministic, explainable Home Finder scoring.

The scorer never fabricates unavailable attributes.  Each component records
whether it was observed, which source supplied it, and how it affected the
final score.  Hard-constraint failures are returned separately from the score.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from kr_apartment_market.home.models import CandidateFacts, CandidateScore, ScoreComponent


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _linear_preference(value: float, ideal: float, worst_distance: float) -> float:
    if worst_distance <= 0:
        return 100.0 if value == ideal else 0.0
    return _clamp(100.0 * (1.0 - abs(value - ideal) / worst_distance))


def _range_overlap_score(
    observed_min: float | None,
    observed_max: float | None,
    preferred_min: float | None,
    preferred_max: float | None,
    target: float | None,
) -> tuple[float | None, str]:
    if observed_min is None and observed_max is None:
        return None, "관측 면적 범위가 없습니다."
    observed_min = observed_min if observed_min is not None else observed_max
    observed_max = observed_max if observed_max is not None else observed_min
    assert observed_min is not None and observed_max is not None
    if target is not None:
        if observed_min <= target <= observed_max:
            return 100.0, f"희망 면적 {target:.1f}㎡가 관측 범위에 포함됩니다."
        distance = min(abs(target - observed_min), abs(target - observed_max))
        return _clamp(100 - distance * 8), f"희망 면적과 가장 가까운 관측 면적 차이는 {distance:.1f}㎡입니다."
    if preferred_min is None and preferred_max is None:
        return None, "희망 면적 범위가 지정되지 않았습니다."
    preferred_min = preferred_min if preferred_min is not None else preferred_max
    preferred_max = preferred_max if preferred_max is not None else preferred_min
    assert preferred_min is not None and preferred_max is not None
    overlap = max(0.0, min(observed_max, preferred_max) - max(observed_min, preferred_min))
    preferred_width = max(1.0, preferred_max - preferred_min)
    if overlap > 0 or (
        observed_min <= preferred_min <= observed_max
        or observed_min <= preferred_max <= observed_max
    ):
        score = 80.0 + 20.0 * min(1.0, overlap / preferred_width)
        return score, "희망 면적 범위와 거래 관측 면적이 겹칩니다."
    distance = min(abs(preferred_min - observed_max), abs(observed_min - preferred_max))
    return _clamp(70 - distance * 8), f"희망 범위와 관측 면적 사이에 {distance:.1f}㎡ 차이가 있습니다."


def _price_component(profile: dict[str, Any], facts: CandidateFacts) -> tuple[float | None, str]:
    budget = profile["budget"]
    transaction_type = profile["transaction_type"]
    price = facts.reference_price_10k_krw
    if price is None:
        return None, "비교 가능한 기준 가격이 없습니다."

    if transaction_type == "sale":
        low = budget.get("min_price_10k_krw")
        high = budget.get("max_price_10k_krw")
    elif transaction_type == "jeonse":
        low = None
        high = budget.get("max_deposit_10k_krw")
    else:
        low = None
        high = budget.get("max_deposit_10k_krw")

    if low is None and high is None:
        return None, "가격 상·하한이 지정되지 않았습니다."
    if high is not None:
        if price <= high:
            if low is not None and price < low:
                width = max(1.0, high - low)
                score = _clamp(80 - (low - price) / width * 30)
                return score, "기준 가격이 희망 최저 예산보다 낮습니다."
            headroom = (high - price) / max(high, 1.0)
            return _clamp(82 + headroom * 36), f"기준 가격이 최대 예산보다 {headroom * 100:.1f}% 낮습니다."
        over = (price - high) / max(high, 1.0)
        return _clamp(60 - over * 200), f"기준 가격이 최대 예산보다 {over * 100:.1f}% 높습니다."
    assert low is not None
    if price >= low:
        return 90.0, "기준 가격이 희망 최저 예산 이상입니다."
    shortfall = (low - price) / max(low, 1.0)
    return _clamp(75 - shortfall * 100), "기준 가격이 희망 최저 예산보다 낮습니다."


def _monthly_rent_budget_component(
    profile: dict[str, Any], facts: CandidateFacts
) -> tuple[float | None, str]:
    if profile["transaction_type"] != "monthly_rent":
        return _price_component(profile, facts)
    budget = profile["budget"]
    deposit = facts.median_monthly_deposit_10k_krw
    rent = facts.median_monthly_rent_10k_krw
    max_deposit = budget.get("max_deposit_10k_krw")
    max_rent = budget.get("max_monthly_rent_10k_krw")
    scores: list[float] = []
    labels: list[str] = []
    if max_deposit is not None and deposit is not None:
        ratio = deposit / max(max_deposit, 1.0)
        scores.append(_clamp(120 - ratio * 40) if ratio <= 1 else _clamp(60 - (ratio - 1) * 200))
        labels.append(f"보증금 {deposit:,.0f}만원")
    if max_rent is not None and rent is not None:
        ratio = rent / max(max_rent, 1.0)
        scores.append(_clamp(120 - ratio * 40) if ratio <= 1 else _clamp(60 - (ratio - 1) * 200))
        labels.append(f"월세 {rent:,.0f}만원")
    if not scores:
        return None, "월세 보증금·월세 비교 데이터가 부족합니다."
    return sum(scores) / len(scores), ", ".join(labels) + " 기준입니다."


def _hard_constraint_failures(
    profile: dict[str, Any], facts: CandidateFacts, *, as_of: date
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unknowns: list[str] = []
    hard = profile["hard_constraints"]
    budget = profile["budget"]
    transaction_type = profile["transaction_type"]

    if hard.get("budget"):
        if transaction_type == "sale":
            max_price = budget.get("max_price_10k_krw")
            if max_price is not None:
                if facts.reference_price_10k_krw is None:
                    unknowns.append("매매 기준 가격")
                elif facts.reference_price_10k_krw > max_price:
                    failures.append("최대 매매 예산 초과")
        elif transaction_type == "jeonse":
            maximum = budget.get("max_deposit_10k_krw")
            if maximum is not None:
                if facts.reference_price_10k_krw is None:
                    unknowns.append("전세 기준 보증금")
                elif facts.reference_price_10k_krw > maximum:
                    failures.append("최대 전세 보증금 초과")
        else:
            maximum_deposit = budget.get("max_deposit_10k_krw")
            maximum_rent = budget.get("max_monthly_rent_10k_krw")
            if maximum_deposit is not None:
                if facts.median_monthly_deposit_10k_krw is None:
                    unknowns.append("월세 보증금")
                elif facts.median_monthly_deposit_10k_krw > maximum_deposit:
                    failures.append("최대 월세 보증금 초과")
            if maximum_rent is not None:
                if facts.median_monthly_rent_10k_krw is None:
                    unknowns.append("월세액")
                elif facts.median_monthly_rent_10k_krw > maximum_rent:
                    failures.append("최대 월세액 초과")

    if hard.get("area"):
        area = profile["area"]
        preferred_min = area.get("min_m2")
        preferred_max = area.get("max_m2")
        if preferred_min is not None or preferred_max is not None:
            if facts.area_min_m2 is None and facts.area_max_m2 is None:
                unknowns.append("면적")
            else:
                observed_min = facts.area_min_m2 if facts.area_min_m2 is not None else facts.area_max_m2
                observed_max = facts.area_max_m2 if facts.area_max_m2 is not None else facts.area_min_m2
                assert observed_min is not None and observed_max is not None
                low = preferred_min if preferred_min is not None else preferred_max
                high = preferred_max if preferred_max is not None else preferred_min
                assert low is not None and high is not None
                if observed_max < low or observed_min > high:
                    failures.append("희망 전용면적 범위 불일치")

    if hard.get("building_age") and profile["building"].get("max_age_years") is not None:
        max_age = profile["building"]["max_age_years"]
        if facts.representative_build_year is None:
            unknowns.append("준공연도")
        elif as_of.year - facts.representative_build_year > max_age:
            failures.append("희망 최대 연식 초과")

    if hard.get("minimum_transactions") and facts.transaction_count < profile["minimum_transactions"]:
        failures.append("최소 거래 표본 수 미달")

    enrichment = facts.enrichment
    if hard.get("parking") and profile["building"].get("min_parking_per_household") is not None:
        observed = enrichment.get("parking_per_household")
        if observed is None:
            unknowns.append("세대당 주차")
        elif float(observed) < profile["building"]["min_parking_per_household"]:
            failures.append("세대당 주차 조건 미달")

    if hard.get("commute") and profile.get("commute"):
        observed = enrichment.get("commute_minutes", {})
        if not isinstance(observed, dict):
            observed = {}
        for destination in profile["commute"]:
            maximum = destination.get("max_minutes")
            value = observed.get(destination["name"])
            if maximum is None:
                continue
            if value is None:
                unknowns.append(f"{destination['name']} 통근시간")
            elif float(value) > maximum:
                failures.append(f"{destination['name']} 통근시간 초과")

    if profile["unknown_policy"] == "exclude" and unknowns:
        failures.extend(f"필수 데이터 없음: {item}" for item in unknowns)
    return failures, unknowns


def score_candidate(
    profile: dict[str, Any], facts: CandidateFacts, *, as_of: date | None = None
) -> CandidateScore:
    """Score one candidate using a normalized profile."""

    as_of = as_of or date.today()
    failures, hard_unknowns = _hard_constraint_failures(profile, facts, as_of=as_of)
    weights: dict[str, float] = profile["weights"]
    components: list[ScoreComponent] = []

    def add(name: str, value: float | None, source: str, explanation: str) -> None:
        components.append(
            ScoreComponent(
                name=name,
                score=round(_clamp(value), 2) if value is not None else None,
                weight=float(weights.get(name, 0.0)),
                available=value is not None,
                source=source,
                explanation=explanation,
            )
        )

    affordability, message = _monthly_rent_budget_component(profile, facts)
    add("affordability", affordability, "MOLIT_TRANSACTION", message)

    area_score, message = _range_overlap_score(
        facts.area_min_m2,
        facts.area_max_m2,
        profile["area"].get("min_m2"),
        profile["area"].get("max_m2"),
        profile["area"].get("target_m2"),
    )
    add("area_fit", area_score, "MOLIT_TRANSACTION", message)

    max_age = profile["building"].get("max_age_years")
    if facts.representative_build_year is None or max_age is None:
        age_score, age_message = None, "희망 연식 또는 관측 준공연도가 없습니다."
    else:
        age = max(0, as_of.year - facts.representative_build_year)
        age_score = 100.0 if age <= max_age else _clamp(100 - (age - max_age) * 8)
        age_message = f"대표 준공연도 {facts.representative_build_year}년, 약 {age}년차입니다."
    add("building_age", age_score, "MOLIT_TRANSACTION", age_message)

    liquidity_score = _clamp(100 * math.log1p(max(facts.transaction_count, 0)) / math.log1p(12))
    add(
        "liquidity",
        liquidity_score,
        "MOLIT_TRANSACTION",
        f"분석 기간 유효 거래 {facts.transaction_count}건입니다.",
    )

    if facts.latest_contract_date:
        try:
            days = max(0, (as_of - date.fromisoformat(facts.latest_contract_date)).days)
            recency_score = _clamp(100 - max(0, days - 14) * 0.32)
            recency_message = f"최신 계약일은 {facts.latest_contract_date}이며 기준일 대비 {days}일 전입니다."
        except ValueError:
            recency_score, recency_message = None, "최신 계약일 형식을 해석하지 못했습니다."
    else:
        recency_score, recency_message = None, "최신 계약일이 없습니다."
    add("recency", recency_score, "MOLIT_TRANSACTION", recency_message)

    if facts.recovery_rate_pct is None:
        recovery_score, recovery_message = None, "최고가 대비 회복률을 계산할 수 없습니다."
    else:
        # This is a market-position score, not a forecast.  Around 90-100% is
        # treated as a strong but not overheated recovery band.
        recovery_score = _linear_preference(facts.recovery_rate_pct, 95.0, 55.0)
        recovery_message = f"최고가 대비 회복률은 {facts.recovery_rate_pct:.2f}%입니다."
    add("recovery", recovery_score, "DERIVED_METRIC", recovery_message)

    preferred_ratio = profile.get("preferences", {}).get("preferred_jeonse_ratio_pct")
    if preferred_ratio is None or facts.jeonse_ratio_pct is None:
        jeonse_score, jeonse_message = None, "선호 전세가율 또는 관측 전세가율이 없습니다."
    else:
        target = float(preferred_ratio)
        jeonse_score = _linear_preference(facts.jeonse_ratio_pct, target, 35.0)
        jeonse_message = f"전세가율 {facts.jeonse_ratio_pct:.2f}%를 선호값 {target:.1f}%와 비교했습니다."
    add("jeonse_safety", jeonse_score, "DERIVED_METRIC", jeonse_message)

    enrichment = facts.enrichment or {}
    commute_observed = enrichment.get("commute_minutes", {})
    commute_scores: list[tuple[float, float]] = []
    commute_messages: list[str] = []
    if isinstance(commute_observed, dict):
        for destination in profile.get("commute", []):
            observed = commute_observed.get(destination["name"])
            maximum = destination.get("max_minutes")
            if observed is None or maximum is None:
                continue
            observed_float = float(observed)
            maximum_float = float(maximum)
            score = 100.0 if observed_float <= maximum_float else _clamp(100 - (observed_float - maximum_float) * 5)
            commute_scores.append((score, float(destination.get("weight") or 1.0)))
            commute_messages.append(f"{destination['name']} {observed_float:.0f}분")
    if commute_scores:
        total_weight = sum(weight for _, weight in commute_scores) or 1.0
        commute_score = sum(score * weight for score, weight in commute_scores) / total_weight
        commute_message = ", ".join(commute_messages) + " 기준입니다."
    else:
        commute_score, commute_message = None, "통근시간 enrichment가 없습니다."
    add("commute", commute_score, "OPTIONAL_ENRICHMENT", commute_message)

    education = enrichment.get("education_score")
    education_score = float(education) if education is not None else None
    add(
        "education",
        education_score,
        "OPTIONAL_ENRICHMENT",
        "교육 환경 점수 enrichment를 사용했습니다." if education is not None else "교육 환경 enrichment가 없습니다.",
    )

    parking = enrichment.get("parking_per_household")
    required_parking = profile["building"].get("min_parking_per_household")
    if parking is None or required_parking is None:
        parking_score, parking_message = None, "세대당 주차 선호 또는 enrichment가 없습니다."
    else:
        ratio = float(parking) / max(float(required_parking), 0.01)
        parking_score = _clamp(60 + ratio * 40) if ratio <= 1 else 100.0
        parking_message = f"세대당 주차 {float(parking):.2f}대를 요구값 {float(required_parking):.2f}대와 비교했습니다."
    add("parking", parking_score, "OPTIONAL_ENRICHMENT", parking_message)

    listing_count = enrichment.get("listing_count")
    if listing_count is None:
        listing_score, listing_message = None, "허가된 현재 광고매물 수 데이터가 없습니다."
    else:
        count = max(0, int(listing_count))
        listing_score = _clamp(100 * math.log1p(count) / math.log1p(15))
        listing_message = f"중복 조정 전 또는 원천 기준 현재 광고매물 {count}건입니다."
    add("listing_availability", listing_score, "AUTHORIZED_LISTING_METADATA", listing_message)

    unknown_policy = profile["unknown_policy"]
    numerator = 0.0
    denominator = 0.0
    available_weight = 0.0
    unknowns = list(dict.fromkeys(hard_unknowns))
    strengths: list[str] = []
    tradeoffs: list[str] = []

    for component in components:
        if component.weight <= 0:
            continue
        if component.score is None:
            unknowns.append(component.name)
            if unknown_policy == "penalize":
                numerator += 40.0 * component.weight
                denominator += component.weight
            continue
        available_weight += component.weight
        numerator += component.score * component.weight
        denominator += component.weight
        if component.score >= 80:
            strengths.append(component.explanation)
        elif component.score < 55:
            tradeoffs.append(component.explanation)

    match_score = numerator / denominator if denominator > 0 else 0.0
    total_weight = sum(component.weight for component in components)
    coverage = available_weight / total_weight if total_weight > 0 else 0.0
    sample_confidence = min(1.0, facts.transaction_count / 5.0)
    if facts.latest_contract_date:
        try:
            recency_days = max(0, (as_of - date.fromisoformat(facts.latest_contract_date)).days)
            recency_confidence = max(0.1, min(1.0, 1 - recency_days / 730))
        except ValueError:
            recency_confidence = 0.25
    else:
        recency_confidence = 0.1
    confidence = 100 * (0.45 * sample_confidence + 0.35 * coverage + 0.20 * recency_confidence)

    return CandidateScore(
        match_score=round(match_score, 2),
        confidence_score=round(_clamp(confidence), 2),
        excluded=bool(failures),
        exclusion_reasons=failures,
        components=components,
        strengths=list(dict.fromkeys(strengths))[:5],
        tradeoffs=list(dict.fromkeys(tradeoffs))[:5],
        unknowns=list(dict.fromkeys(unknowns)),
        available_weight=round(available_weight, 6),
        total_weight=round(total_weight, 6),
    )
