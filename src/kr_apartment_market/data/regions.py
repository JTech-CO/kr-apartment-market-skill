"""Offline legal-district resolver backed by a packaged region table."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any


@dataclass(frozen=True, slots=True)
class Region:
    lawd_code: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"lawd_code": self.lawd_code, "name": self.name}


@lru_cache(maxsize=1)
def load_regions() -> tuple[Region, ...]:
    resource = files("kr_apartment_market.resources").joinpath("region_codes.tsv")
    rows: list[Region] = []
    with resource.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            code = (row.get("code") or "").strip()
            name = (row.get("name") or "").strip()
            if re.fullmatch(r"\d{5}", code) and name:
                rows.append(Region(code, name))
    return tuple(rows)


def resolve_region(query: str, limit: int = 10) -> dict[str, Any]:
    raw = query.strip()
    if not raw:
        raise ValueError("query must not be empty")
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")

    if re.fullmatch(r"\d{5}", raw):
        matches = [region for region in load_regions() if region.lawd_code == raw]
        if matches:
            return {"normalized_query": raw, "matches": [matches[0].to_dict()]}
        return {
            "normalized_query": raw,
            "matches": [{"lawd_code": raw, "name": "사용자 입력 법정동 코드"}],
            "notices": ["패키지 지역표에 없지만 형식이 유효한 5자리 코드로 처리했습니다."],
        }

    if re.fullmatch(r"\d{10}", raw):
        return resolve_region(raw[:5], limit=limit)

    aliases = {
        "서울": "서울특별시",
        "부산": "부산광역시",
        "대구": "대구광역시",
        "인천": "인천광역시",
        "광주": "광주광역시",
        "대전": "대전광역시",
        "울산": "울산광역시",
        "세종": "세종특별자치시",
        "강원도": "강원특별자치도",
        "전라북도": "전북특별자치도",
        "전북": "전북특별자치도",
        "제주도": "제주특별자치도",
    }
    normalized = raw
    for short, full in aliases.items():
        normalized = re.sub(rf"(?<![가-힣]){re.escape(short)}(?![가-힣])", full, normalized)
    tokens = [token for token in re.split(r"\s+", normalized) if token]

    scored: list[tuple[int, Region]] = []
    for region in load_regions():
        if all(token in region.name for token in tokens):
            exact_bonus = 100 if normalized == region.name else 0
            suffix_bonus = sum(5 for token in tokens if region.name.endswith(token))
            scored.append((exact_bonus + suffix_bonus + len("".join(tokens)), region))

    scored.sort(key=lambda item: (-item[0], item[1].name, item[1].lawd_code))
    matches = [region.to_dict() for _, region in scored[:limit]]
    return {"normalized_query": normalized, "matches": matches}
