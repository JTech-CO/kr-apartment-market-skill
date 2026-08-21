"""Normalized transaction and source models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PropertyType = Literal["apartment", "officetel", "villa", "house", "commercial"]
TradeType = Literal["sale", "rent"]


@dataclass(slots=True)
class SourceReference:
    source: str
    provider: str
    lawd_code: str | None = None
    deal_months: list[str] = field(default_factory=list)
    access: str = "API"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Transaction:
    source_record_id: str
    source: str
    property_type: PropertyType
    trade_type: TradeType
    lawd_code: str
    contract_date: str | None
    complex_name: str | None
    dong: str | None
    area_m2: float | None
    floor: int | None
    build_year: int | None
    price_10k_krw: int | None = None
    deposit_10k_krw: int | None = None
    monthly_rent_10k_krw: int | None = None
    rent_type: str | None = None
    deal_type: str | None = None
    house_type: str | None = None
    is_canceled: bool = False
    canceled_at: str | None = None
    collected_at: str | None = None
    raw: dict[str, str] | None = None

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        result = asdict(self)
        if not include_raw:
            result.pop("raw", None)
        return result
