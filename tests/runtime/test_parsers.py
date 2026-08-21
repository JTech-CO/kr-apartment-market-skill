from defusedxml.ElementTree import fromstring

from kr_apartment_market.data.public_data import _normalize_item
from real_estate.mcp_server.parsers.rent import _parse_apt_rent
from real_estate.mcp_server.parsers.trade import _parse_apt_trades

TRADE_XML = """
<response><header><resultCode>000</resultCode></header><body><totalCount>2</totalCount><items>
<item><aptNm>A단지</aptNm><umdNm>역삼동</umdNm><excluUseAr>84.9</excluUseAr><floor>10</floor><dealAmount>120,000</dealAmount><dealYear>2026</dealYear><dealMonth>8</dealMonth><dealDay>1</dealDay><buildYear>2000</buildYear><dealingGbn>중개거래</dealingGbn></item>
<item><aptNm>A단지</aptNm><umdNm>역삼동</umdNm><excluUseAr>84.9</excluUseAr><floor>9</floor><dealAmount>119,000</dealAmount><dealYear>2026</dealYear><dealMonth>8</dealMonth><dealDay>2</dealDay><cdealType>O</cdealType><cdealDay>20260810</cdealDay></item>
</items></body></response>
"""

RENT_XML = """
<response><header><resultCode>000</resultCode></header><body><totalCount>1</totalCount><items>
<item><aptNm>A단지</aptNm><umdNm>역삼동</umdNm><excluUseAr>84.9</excluUseAr><floor>5</floor><deposit>70,000</deposit><monthlyRent>0</monthlyRent><dealYear>2026</dealYear><dealMonth>8</dealMonth><dealDay>3</dealDay></item>
</items></body></response>
"""


def test_compat_trade_parser_excludes_canceled():
    rows, error = _parse_apt_trades(TRADE_XML)
    assert error is None
    assert len(rows) == 1
    assert rows[0]["price_10k"] == 120000


def test_compat_rent_parser():
    rows, error = _parse_apt_rent(RENT_XML)
    assert error is None
    assert rows[0]["deposit_10k"] == 70000


def test_canonical_parser_preserves_cancellation():
    root = fromstring(TRADE_XML)
    item = root.findall(".//item")[1]
    tx = _normalize_item(
        item,
        property_type="apartment",
        trade_type="sale",
        lawd_code="11680",
        collected_at="2026-08-22T00:00:00+09:00",
        occurrence=0,
    )
    assert tx is not None
    assert tx.is_canceled is True
    assert tx.canceled_at == "2026-08-10"
