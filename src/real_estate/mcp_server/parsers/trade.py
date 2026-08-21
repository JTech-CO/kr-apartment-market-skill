"""Upstream-compatible XML trade parsers retained for fixture compatibility."""

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
        if _txt(item, "cdealType").upper() == "O" or _txt(item, "cdealtype").upper() == "O":
            continue
        price_raw = _txt(item, "dealAmount")
        if not price_raw:
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
        elif kind == "house":
            name = ""
            area = _float(_txt(item, "totalFloorAr"))
        else:
            rows.append(
                {
                    "building_type": _txt(item, "buildingType"),
                    "building_use": _txt(item, "buildingUse"),
                    "land_use": _txt(item, "landUse"),
                    "dong": _txt(item, "umdNm"),
                    "building_ar": _float(_txt(item, "buildingAr")),
                    "floor": _int(_txt(item, "floor")),
                    "price_10k": _int(price_raw),
                    "trade_date": _date(item),
                    "build_year": _int(_txt(item, "buildYear")),
                    "deal_type": _txt(item, "dealingGbn"),
                    "share_dealing": _txt(item, "shareDealingType"),
                }
            )
            continue
        row = {
            "unit_name": name,
            "dong": _txt(item, "umdNm"),
            "area_sqm": area,
            "floor": _int(_txt(item, "floor")),
            "price_10k": _int(price_raw),
            "trade_date": _date(item),
            "build_year": _int(_txt(item, "buildYear")),
            "deal_type": _txt(item, "dealingGbn"),
        }
        if kind == "apartment":
            row["apt_name"] = row.pop("unit_name")
        if kind in {"villa", "house"}:
            row["house_type"] = _txt(item, "houseType")
        rows.append(row)
    return rows, None


def _parse_apt_trades(xml_text: str):
    return _parse(xml_text, "apartment")


def _parse_officetel_trades(xml_text: str):
    return _parse(xml_text, "officetel")


def _parse_villa_trades(xml_text: str):
    return _parse(xml_text, "villa")


def _parse_single_house_trades(xml_text: str):
    return _parse(xml_text, "house")


def _parse_commercial_trade(xml_text: str):
    return _parse(xml_text, "commercial")
