"""Upstream-compatible XML rent parsers retained for fixture compatibility."""

from __future__ import annotations

from typing import Any

from defusedxml.ElementTree import fromstring


def _txt(item: Any, name: str) -> str:
    return (item.findtext(name) or "").strip()


def _int(raw: str) -> int:
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        return 0


def _float(raw: str) -> float:
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _date(item: Any) -> str:
    year = _txt(item, "dealYear")
    if not year:
        return ""
    return f"{year}-{_txt(item, 'dealMonth').zfill(2)}-{_txt(item, 'dealDay').zfill(2)}"


def _parse(xml_text: str, kind: str) -> tuple[list[dict[str, Any]], str | None]:
    root = fromstring(xml_text)
    code = root.findtext(".//resultCode") or ""
    if code not in {"000", "00", "0"}:
        return [], code
    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        deposit_raw = _txt(item, "deposit")
        if not deposit_raw:
            continue
        if kind == "apartment":
            name = _txt(item, "aptNm")
            area = _float(_txt(item, "excluUseAr"))
        elif kind == "officetel":
            name = _txt(item, "offiNm")
            area = _float(_txt(item, "excluUseAr"))
        elif kind == "villa":
            name = _txt(item, "mhouseNm")
            area = _float(_txt(item, "excluUseAr"))
        else:
            name = ""
            area = _float(_txt(item, "totalFloorAr"))
        row = {
            "unit_name": name,
            "dong": _txt(item, "umdNm"),
            "area_sqm": area,
            "floor": _int(_txt(item, "floor")),
            "deposit_10k": _int(deposit_raw),
            "monthly_rent_10k": _int(_txt(item, "monthlyRent")),
            "contract_type": _txt(item, "contractType"),
            "trade_date": _date(item),
            "build_year": _int(_txt(item, "buildYear")),
        }
        if kind in {"villa", "house"}:
            row["house_type"] = _txt(item, "houseType")
        rows.append(row)
    return rows, None


def _parse_apt_rent(xml_text: str):
    return _parse(xml_text, "apartment")


def _parse_officetel_rent(xml_text: str):
    return _parse(xml_text, "officetel")


def _parse_villa_rent(xml_text: str):
    return _parse(xml_text, "villa")


def _parse_single_house_rent(xml_text: str):
    return _parse(xml_text, "house")
