from datetime import date

from kr_apartment_market.models import Transaction
from kr_apartment_market.services.metrics import (
    build_region_pulse,
    build_snapshot,
    detect_signals,
)


def tx(day: str, price: int, name: str = "테스트단지") -> Transaction:
    return Transaction(
        source_record_id=f"{day}-{price}",
        source="fixture",
        property_type="apartment",
        trade_type="sale",
        lawd_code="11680",
        contract_date=day,
        complex_name=name,
        dong="역삼동",
        area_m2=84.9,
        floor=10,
        build_year=2000,
        price_10k_krw=price,
    )


def rent(day: str, deposit: int, monthly: int = 0) -> Transaction:
    return Transaction(
        source_record_id=f"rent-{day}-{deposit}",
        source="fixture",
        property_type="apartment",
        trade_type="rent",
        lawd_code="11680",
        contract_date=day,
        complex_name="테스트단지",
        dong="역삼동",
        area_m2=84.9,
        floor=10,
        build_year=2000,
        deposit_10k_krw=deposit,
        monthly_rent_10k_krw=monthly,
    )


def test_snapshot_metrics_and_jeonse_only():
    sales = [tx("2026-06-01", 100000), tx("2026-07-01", 120000), tx("2026-08-01", 110000)]
    rents = [rent("2026-08-01", 70000), rent("2026-08-02", 10000, 200)]
    snapshot = build_snapshot(sales, rents, as_of=date(2026, 8, 10))
    assert snapshot["median_sale_price_10k_krw"] == 110000
    assert snapshot["historical_peak_10k_krw"] == 120000
    assert snapshot["recovery_rate_pct"] == 91.67
    assert snapshot["median_jeonse_deposit_10k_krw"] == 70000
    assert snapshot["jeonse_ratio_pct"] == 63.64
    assert snapshot["estimated_gap_10k_krw"] == 40000


def test_region_pulse_zero_baseline_is_reopened():
    sales = [tx("2026-08-05", 100000)]
    pulse = build_region_pulse(sales, as_of=date(2026, 8, 10))
    assert pulse["comparison_state"] == "REOPENED"
    assert pulse["volume_change_pct"] is None


def test_signal_detection():
    sales = [
        tx("2025-01-01", 90000),
        tx("2025-05-01", 100000),
        tx("2026-01-01", 110000),
    ]
    signals = detect_signals(sales)
    types = [item["type"] for item in signals]
    assert "NEW_HIGH" in types
    assert "TRANSACTION_RESUMED" in types
