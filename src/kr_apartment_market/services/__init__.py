"""Deterministic analytics and local persistence services."""

from .finance import (
    calculate_compound_growth,
    calculate_loan_payment,
    calculate_monthly_cashflow,
)
from .metrics import (
    build_region_pulse,
    build_snapshot,
    detect_signals,
    group_by_complex,
    quality_grade,
    rank_complexes,
)
from .watchlist import WatchlistStore

__all__ = [
    "WatchlistStore",
    "build_region_pulse",
    "build_snapshot",
    "calculate_compound_growth",
    "calculate_loan_payment",
    "calculate_monthly_cashflow",
    "detect_signals",
    "group_by_complex",
    "quality_grade",
    "rank_complexes",
]
