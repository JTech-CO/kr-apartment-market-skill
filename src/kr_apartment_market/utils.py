"""Date, number and identifier utilities."""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


def now_iso(timezone: str = "Asia/Seoul") -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    raw = str(value).replace(",", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_float(value: str | float | None) -> float | None:
    if value is None:
        return None
    raw = str(value).replace(",", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_date_parts(year: str | None, month: str | None, day: str | None) -> str | None:
    if not year:
        return None
    try:
        return date(int(year), int(month or 1), int(day or 1)).isoformat()
    except ValueError:
        return None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", value).casefold()


def stable_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def parse_date_bound(value: str | None, *, is_end: bool, today: date | None = None) -> date:
    today = today or date.today()
    if not value:
        return today
    raw = value.strip()
    if re.fullmatch(r"\d{6}", raw):
        year, month = int(raw[:4]), int(raw[4:])
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return date(year, month, day)
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        year, month = map(int, raw.split("-"))
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return date(year, month, day)
    return date.fromisoformat(raw)


def iter_months(start: date, end: date, max_months: int) -> list[str]:
    if start > end:
        raise ValueError("date_from must not be after date_to")
    result: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        result.append(f"{year:04d}{month:02d}")
        if len(result) > max_months:
            raise ValueError(f"requested period exceeds max_months={max_months}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return result
