#!/usr/bin/env python3
"""Generate the canonical MCP JSON catalog from a compact source definition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STRING = {"type": "string"}
NUMBER = {"type": "number"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_NUMBER = {"type": ["number", "null"]}


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


ENVELOPE = object_schema(
    {
        "answered_at": STRING,
        "timezone": STRING,
        "data": {},
        "sources": {"type": "array", "items": {"type": "object"}},
        "notices": {"type": "array", "items": STRING},
        "error": {"type": "object"},
    },
    ["answered_at", "timezone", "data", "sources", "notices"],
)

COMMON_DATES = {
    "date_from": NULLABLE_STRING,
    "date_to": NULLABLE_STRING,
}
COMMON_AREAS = {
    "area_m2": NULLABLE_NUMBER,
    "area_tolerance_m2": {"type": "number", "minimum": 0, "default": 1.0},
    "area_min_m2": NULLABLE_NUMBER,
    "area_max_m2": NULLABLE_NUMBER,
}

TOOLS: list[dict[str, Any]] = []


def add(name: str, title: str, description: str, schema: dict[str, Any]) -> None:
    TOOLS.append(
        {
            "name": name,
            "title": title,
            "description": description,
            "inputSchema": schema,
            "outputSchema": ENVELOPE,
            "annotations": {"readOnlyHint": not any(x in name for x in ["upsert", "delete"])},
        }
    )


add(
    "kr_apartment.resolve_location",
    "지역 코드 해석",
    "한국어 지역명 또는 5/10자리 법정동 코드를 LAWD_CD 후보로 해석합니다.",
    object_schema({"query": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}}, ["query"]),
)
add(
    "kr_apartment.get_transactions",
    "통합 실거래 조회",
    "국토교통부 공개 API에서 여러 부동산 유형의 매매·전월세 거래를 조회하고 정규화합니다.",
    object_schema(
        {
            "lawd_code": STRING,
            "property_type": {"type": "string", "enum": ["apartment", "officetel", "villa", "house", "commercial"], "default": "apartment"},
            "trade_type": {"type": "string", "enum": ["sale", "rent"], "default": "sale"},
            **COMMON_DATES,
            "complex_name": NULLABLE_STRING,
            **COMMON_AREAS,
            "include_canceled": {"type": "boolean", "default": False},
            "include_raw": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
        },
        ["lawd_code"],
    ),
)
add(
    "kr_apartment.search_complexes",
    "단지 검색",
    "지역과 기간의 아파트 매매 자료에서 단지명과 관측 면적 범위를 찾습니다.",
    object_schema({"lawd_code": STRING, "query": STRING, **COMMON_DATES, "area_min_m2": NULLABLE_NUMBER, "area_max_m2": NULLABLE_NUMBER, "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}}, ["lawd_code"]),
)
add(
    "kr_apartment.get_complex_snapshot",
    "단지 스냅샷",
    "동일 면적 기준 매매·전세 중위값, 회복률, 전세가율, 추정 갭과 거래량을 계산합니다.",
    object_schema({"lawd_code": STRING, "complex_name": STRING, **COMMON_DATES, "area_m2": NULLABLE_NUMBER, "area_tolerance_m2": COMMON_AREAS["area_tolerance_m2"]}, ["lawd_code", "complex_name"]),
)
add(
    "kr_apartment.compare_complexes",
    "단지 비교",
    "2~10개 단지를 같은 기간과 면적 오차로 비교합니다.",
    object_schema({"complexes": {"type": "array", "minItems": 2, "maxItems": 10, "items": object_schema({"lawd_code": STRING, "complex_name": STRING, "area_m2": NULLABLE_NUMBER}, ["lawd_code", "complex_name"])}, **COMMON_DATES, "area_tolerance_m2": COMMON_AREAS["area_tolerance_m2"]}, ["complexes"]),
)
add(
    "kr_apartment.get_region_pulse",
    "지역 시장 펄스",
    "최근 30일과 직전 30일의 거래량 및 중위가격을 비교합니다.",
    object_schema({"lawd_code": STRING, **COMMON_DATES, "area_min_m2": NULLABLE_NUMBER, "area_max_m2": NULLABLE_NUMBER}, ["lawd_code"]),
)
add(
    "kr_apartment.rank_complexes",
    "단지 순위",
    "지역 내 단지를 거래량·중위가·회복률·모멘텀·전세가율·추정 갭으로 정렬합니다.",
    object_schema({"lawd_code": STRING, "metric": {"type": "string", "enum": ["transaction_volume", "median_price", "recovery_rate", "volume_momentum", "jeonse_ratio", "estimated_gap"], "default": "transaction_volume"}, **COMMON_DATES, "area_min_m2": NULLABLE_NUMBER, "area_max_m2": NULLABLE_NUMBER, "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}, ["lawd_code"]),
)
add(
    "kr_apartment.get_signal_feed",
    "시장 이벤트",
    "신고가와 거래 재개 조건을 만족한 결정론적 이벤트를 반환합니다.",
    object_schema({"lawd_code": STRING, **COMMON_DATES, "area_min_m2": NULLABLE_NUMBER, "area_max_m2": NULLABLE_NUMBER, "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100}}, ["lawd_code"]),
)
add("kr_apartment.get_data_freshness", "데이터 최신성", "최신 신고 실거래의 의미와 한계를 설명합니다.", object_schema({}))
add(
    "kr_apartment.get_source_link",
    "원문 링크",
    "국토교통부·아파트Me·프로젝트 원문 링크를 반환합니다. 아파트Me는 LINK_OUT_ONLY입니다.",
    object_schema({"source": {"type": "string", "enum": ["molit", "apt2me", "github", "landing"], "default": "molit"}, "entity_type": {"type": "string", "default": "home"}, "lawd_code": NULLABLE_STRING}),
)
add(
    "kr_apartment.calculate_loan_payment",
    "대출 상환 계산",
    "입력 가정에 따른 원리금균등 또는 원금균등 상환액을 계산합니다.",
    object_schema({"principal_10k": {"type": "number", "exclusiveMinimum": 0}, "annual_rate_pct": {"type": "number", "minimum": 0}, "years": {"type": "integer", "minimum": 1}, "repayment_method": {"type": "string", "enum": ["equal_payment", "equal_principal"], "default": "equal_payment"}}, ["principal_10k", "annual_rate_pct", "years"]),
)
add(
    "kr_apartment.calculate_compound_growth",
    "복리 계산",
    "초기 자산과 월 납입액의 가정 수익률 기반 복리 성장을 계산합니다.",
    object_schema({"initial_10k": {"type": "number", "minimum": 0}, "monthly_contribution_10k": {"type": "number", "minimum": 0}, "annual_rate_pct": {"type": "number", "minimum": 0}, "years": {"type": "integer", "minimum": 1}}, ["initial_10k", "monthly_contribution_10k", "annual_rate_pct", "years"]),
)
add(
    "kr_apartment.calculate_monthly_cashflow",
    "월 현금흐름 계산",
    "소득·대출·생활비·기타 비용·임대수입을 이용해 월 현금흐름을 계산합니다.",
    object_schema({"monthly_income_10k": {"type": "number", "minimum": 0}, "monthly_loan_payment_10k": {"type": "number", "minimum": 0}, "monthly_living_cost_10k": {"type": "number", "minimum": 0}, "other_monthly_costs_10k": {"type": "number", "minimum": 0, "default": 0}, "monthly_rent_income_10k": {"type": "number", "minimum": 0, "default": 0}}, ["monthly_income_10k", "monthly_loan_payment_10k", "monthly_living_cost_10k"]),
)
add("kr_apartment.get_watchlist", "관심 목록", "로컬 단일 사용자 관심 목록을 조회합니다.", object_schema({"profile_id": {"type": "string", "default": "default"}}))
add(
    "kr_apartment.upsert_watchlist_item",
    "관심 단지 저장",
    "관심 단지를 추가하거나 수정합니다.",
    object_schema({"lawd_code": STRING, "complex_name": STRING, "profile_id": {"type": "string", "default": "default"}, "area_m2": NULLABLE_NUMBER, "label": NULLABLE_STRING, "item_id": NULLABLE_STRING}, ["lawd_code", "complex_name"]),
)
TOOLS[-1]["annotations"] = {"readOnlyHint": False, "idempotentHint": True}
add(
    "kr_apartment.delete_watchlist_item",
    "관심 단지 삭제",
    "관심 목록 항목을 삭제합니다.",
    object_schema({"item_id": STRING, "profile_id": {"type": "string", "default": "default"}}, ["item_id"]),
)
TOOLS[-1]["annotations"] = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True}
add(
    "kr_apartment.get_watchlist_brief",
    "관심 단지 브리핑",
    "관심 단지의 현재 스냅샷을 조회합니다.",
    object_schema({"profile_id": {"type": "string", "default": "default"}, **COMMON_DATES, "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20}}),
)


def main() -> None:
    output = Path("mcp/tool-definitions.json")
    payload = {
        "catalogVersion": "2.0.0",
        "mcpProtocolVersion": "2026-07-28",
        "server": {
            "name": "kr-apartment-market",
            "transports": ["stdio", "streamable_http"],
            "timezone": "Asia/Seoul",
        },
        "tools": TOOLS,
        "compatibility": {
            "upstream": "tae0y/real-estate-mcp",
            "enabledByDefault": True,
            "canonicalToolCount": len(TOOLS),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(TOOLS)} tools to {output}")


if __name__ == "__main__":
    main()
