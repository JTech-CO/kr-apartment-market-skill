"""MOLIT/public-data adapters with pagination, retries and normalization."""

from __future__ import annotations

import asyncio
import math
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as safe_fromstring

from kr_apartment_market.config import Settings, get_settings
from kr_apartment_market.models import PropertyType, TradeType, Transaction
from kr_apartment_market.utils import (
    iter_months,
    now_iso,
    parse_date_bound,
    parse_date_parts,
    parse_float,
    parse_int,
    stable_id,
)

_ENDPOINTS: dict[tuple[PropertyType, TradeType], str] = {
    ("apartment", "sale"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/"
        "getRTMSDataSvcAptTrade"
    ),
    ("apartment", "rent"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/"
        "getRTMSDataSvcAptRent"
    ),
    ("officetel", "sale"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/"
        "getRTMSDataSvcOffiTrade"
    ),
    ("officetel", "rent"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/"
        "getRTMSDataSvcOffiRent"
    ),
    ("villa", "sale"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/"
        "getRTMSDataSvcRHTrade"
    ),
    ("villa", "rent"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/"
        "getRTMSDataSvcRHRent"
    ),
    ("house", "sale"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcSHTrade/"
        "getRTMSDataSvcSHTrade"
    ),
    ("house", "rent"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcSHRent/"
        "getRTMSDataSvcSHRent"
    ),
    ("commercial", "sale"): (
        "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/"
        "getRTMSDataSvcNrgTrade"
    ),
}

_API_MESSAGES = {
    "03": "지정한 지역과 기간에 거래 자료가 없습니다.",
    "10": "공공데이터 API 요청 파라미터가 올바르지 않습니다.",
    "22": "공공데이터 API 일일 호출 한도를 초과했습니다.",
    "30": "공공데이터 API 키가 등록되지 않았습니다.",
    "31": "공공데이터 API 키가 만료되었습니다.",
}


class PublicDataError(RuntimeError):
    """Normalized public-data failure without secret leakage."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


@dataclass(slots=True)
class QueryResult:
    transactions: list[Transaction]
    deal_months: list[str]
    total_source_count: int
    collected_at: str


def _txt(item: Any, *names: str) -> str | None:
    for name in names:
        value = item.findtext(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _raw_item(item: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for child in list(item):
        if child.tag and child.text is not None:
            result[str(child.tag)] = child.text.strip()
    return result


def _cancel_date(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
        except ValueError:
            return raw
    return raw


def _normalize_item(
    item: Any,
    *,
    property_type: PropertyType,
    trade_type: TradeType,
    lawd_code: str,
    collected_at: str,
    occurrence: int,
) -> Transaction | None:
    raw = _raw_item(item)
    contract_date = parse_date_parts(
        _txt(item, "dealYear"),
        _txt(item, "dealMonth"),
        _txt(item, "dealDay"),
    )
    complex_name = _txt(item, "aptNm", "offiNm", "mhouseNm", "houseName")
    dong = _txt(item, "umdNm", "sggNm")
    if property_type == "commercial":
        complex_name = _txt(item, "buildingUse", "buildingType")
        area = parse_float(_txt(item, "buildingAr", "landAr"))
    elif property_type == "house":
        area = parse_float(_txt(item, "totalFloorAr", "plottageAr"))
    else:
        area = parse_float(_txt(item, "excluUseAr", "excluUseArea"))

    price = parse_int(_txt(item, "dealAmount")) if trade_type == "sale" else None
    deposit = parse_int(_txt(item, "deposit")) if trade_type == "rent" else None
    monthly_rent = parse_int(_txt(item, "monthlyRent")) if trade_type == "rent" else None
    if trade_type == "sale" and price is None:
        return None
    if trade_type == "rent" and deposit is None and monthly_rent is None:
        return None

    cancel_type = (_txt(item, "cdealType", "cdealtype") or "").upper()
    canceled_raw = _txt(item, "cdealDay", "cdealDate")
    is_canceled = cancel_type == "O" or bool(canceled_raw)
    payload = {
        "source": "molit",
        "property_type": property_type,
        "trade_type": trade_type,
        "lawd_code": lawd_code,
        "raw": raw,
        "occurrence": occurrence,
    }
    return Transaction(
        source_record_id=stable_id(payload),
        source="molit_public_data",
        property_type=property_type,
        trade_type=trade_type,
        lawd_code=lawd_code,
        contract_date=contract_date,
        complex_name=complex_name,
        dong=dong,
        area_m2=area,
        floor=parse_int(_txt(item, "floor")),
        build_year=parse_int(_txt(item, "buildYear")),
        price_10k_krw=price,
        deposit_10k_krw=deposit,
        monthly_rent_10k_krw=monthly_rent,
        rent_type=("monthly_rent" if trade_type == "rent" and (monthly_rent or 0) > 0 else "jeonse" if trade_type == "rent" else None),
        deal_type=_txt(item, "dealingGbn", "contractType"),
        house_type=_txt(item, "houseType", "buildingType"),
        is_canceled=is_canceled,
        canceled_at=_cancel_date(canceled_raw),
        collected_at=collected_at,
        raw=raw,
    )


def _encode_key(key: str) -> str:
    # Public Data Portal exposes both decoded and URL-encoded keys. Preserve an
    # already encoded key, otherwise encode exactly once.
    if "%" in key and urllib.parse.unquote(key) != key:
        return key
    return urllib.parse.quote(key, safe="")


class PublicDataClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or get_settings()
        self._http_client = http_client

    def _require_key(self) -> str:
        key = self.settings.data_go_kr_api_key
        if not key:
            raise PublicDataError(
                "MISSING_DATA_GO_KR_API_KEY",
                "DATA_GO_KR_API_KEY 환경 변수가 필요합니다.",
            )
        return key

    def _url(
        self,
        endpoint: str,
        *,
        key: str,
        lawd_code: str,
        deal_month: str,
        page: int,
    ) -> str:
        return (
            f"{endpoint}?serviceKey={_encode_key(key)}"
            f"&LAWD_CD={urllib.parse.quote(lawd_code)}"
            f"&DEAL_YMD={urllib.parse.quote(deal_month)}"
            f"&numOfRows={self.settings.page_size}&pageNo={page}"
        )

    async def _request(self, url: str) -> str:
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(
            timeout=float(self.settings.http_timeout_seconds)
        )
        try:
            for attempt in range(self.settings.retry_count + 1):
                try:
                    response = await client.get(url)
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        if attempt < self.settings.retry_count:
                            await asyncio.sleep(min(2**attempt, 8))
                            continue
                    response.raise_for_status()
                    return response.text
                except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
                    if attempt >= self.settings.retry_count:
                        status = (
                            exc.response.status_code
                            if isinstance(exc, httpx.HTTPStatusError)
                            else None
                        )
                        suffix = f" (HTTP {status})" if status is not None else ""
                        raise PublicDataError(
                            "PUBLIC_DATA_ERROR",
                            f"공공데이터 원천 요청에 실패했습니다{suffix}.",
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
        finally:
            if owns_client:
                await client.aclose()
        raise AssertionError("unreachable")

    @staticmethod
    def _parse_page(xml_text: str) -> tuple[Any, int, str | None]:
        try:
            root = safe_fromstring(xml_text)
        except ParseError as exc:
            raise PublicDataError(
                "PUBLIC_DATA_RESPONSE_ERROR", "공공데이터 XML 응답을 해석하지 못했습니다."
            ) from exc

        code = (root.findtext(".//resultCode") or "").strip()
        if code and code not in {"000", "00", "0"}:
            message = (root.findtext(".//resultMsg") or "").strip()
            raise PublicDataError(
                "PUBLIC_DATA_RESPONSE_ERROR",
                _API_MESSAGES.get(code, message or f"원천 오류 코드 {code}"),
            )
        try:
            total = int((root.findtext(".//totalCount") or "0").strip())
        except ValueError:
            total = 0
        return root, total, code or None

    async def fetch_transactions(
        self,
        *,
        property_type: PropertyType,
        trade_type: TradeType,
        lawd_code: str,
        date_from: str | None = None,
        date_to: str | None = None,
        complex_name: str | None = None,
        area_m2: float | None = None,
        area_tolerance_m2: float = 1.0,
        area_min_m2: float | None = None,
        area_max_m2: float | None = None,
        include_canceled: bool = False,
    ) -> QueryResult:
        if (property_type, trade_type) not in _ENDPOINTS:
            raise ValueError(f"unsupported property/trade combination: {property_type}/{trade_type}")
        if len(lawd_code) != 5 or not lawd_code.isdigit():
            raise ValueError("lawd_code must be a 5-digit string")
        if area_tolerance_m2 < 0:
            raise ValueError("area_tolerance_m2 must be >= 0")

        end = parse_date_bound(date_to, is_end=True)
        today = date.today()
        if end > today:
            end = today
        start = parse_date_bound(date_from, is_end=False) if date_from else date(end.year, end.month, 1)
        months = iter_months(start, end, self.settings.max_months)
        key = self._require_key()
        endpoint = _ENDPOINTS[(property_type, trade_type)]
        collected_at = now_iso(self.settings.timezone)
        transactions: list[Transaction] = []
        total_source_count = 0
        fingerprints: Counter[str] = Counter()

        for deal_month in months:
            first_url = self._url(
                endpoint, key=key, lawd_code=lawd_code, deal_month=deal_month, page=1
            )
            first_xml = await self._request(first_url)
            root, total, _ = self._parse_page(first_xml)
            total_source_count += total
            pages = max(1, math.ceil(total / self.settings.page_size))
            if pages > self.settings.max_pages:
                raise PublicDataError(
                    "PAGE_LIMIT_EXCEEDED",
                    f"원천 응답이 페이지 상한({self.settings.max_pages})을 초과했습니다. 범위를 줄이세요.",
                )

            page_roots = [root]
            for page in range(2, pages + 1):
                url = self._url(
                    endpoint,
                    key=key,
                    lawd_code=lawd_code,
                    deal_month=deal_month,
                    page=page,
                )
                xml_text = await self._request(url)
                page_root, _, _ = self._parse_page(xml_text)
                page_roots.append(page_root)

            for page_root in page_roots:
                for item in page_root.findall(".//item"):
                    raw = _raw_item(item)
                    fingerprint = stable_id(raw)
                    occurrence = fingerprints[fingerprint]
                    fingerprints[fingerprint] += 1
                    tx = _normalize_item(
                        item,
                        property_type=property_type,
                        trade_type=trade_type,
                        lawd_code=lawd_code,
                        collected_at=collected_at,
                        occurrence=occurrence,
                    )
                    if tx is not None:
                        transactions.append(tx)

        name_filter = "".join((complex_name or "").split()).casefold()
        filtered: list[Transaction] = []
        for tx in transactions:
            if tx.contract_date:
                tx_date = date.fromisoformat(tx.contract_date)
                if tx_date < start or tx_date > end:
                    continue
            if not include_canceled and tx.is_canceled:
                continue
            if name_filter:
                candidate = "".join((tx.complex_name or "").split()).casefold()
                if name_filter not in candidate:
                    continue
            if area_m2 is not None:
                if tx.area_m2 is None or abs(tx.area_m2 - area_m2) > area_tolerance_m2:
                    continue
            if area_min_m2 is not None and (tx.area_m2 is None or tx.area_m2 < area_min_m2):
                continue
            if area_max_m2 is not None and (tx.area_m2 is None or tx.area_m2 > area_max_m2):
                continue
            filtered.append(tx)

        filtered.sort(key=lambda tx: (tx.contract_date or "", tx.source_record_id), reverse=True)
        return QueryResult(
            transactions=filtered,
            deal_months=months,
            total_source_count=total_source_count,
            collected_at=collected_at,
        )
