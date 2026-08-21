"""Deterministic financial calculators; outputs are assumptions, not approvals."""

from __future__ import annotations

from typing import Any


def calculate_loan_payment(
    principal_10k: float,
    annual_rate_pct: float,
    years: int,
    repayment_method: str = "equal_payment",
) -> dict[str, Any]:
    if principal_10k <= 0:
        raise ValueError("principal_10k must be > 0")
    if annual_rate_pct < 0:
        raise ValueError("annual_rate_pct must be >= 0")
    if years < 1:
        raise ValueError("years must be >= 1")
    if repayment_method not in {"equal_payment", "equal_principal"}:
        raise ValueError("repayment_method must be equal_payment or equal_principal")
    months = years * 12
    monthly_rate = annual_rate_pct / 100 / 12
    if repayment_method == "equal_payment":
        if monthly_rate == 0:
            monthly = principal_10k / months
        else:
            factor = (1 + monthly_rate) ** months
            monthly = principal_10k * monthly_rate * factor / (factor - 1)
        total = monthly * months
        first = last = monthly
    else:
        principal_part = principal_10k / months
        first = principal_part + principal_10k * monthly_rate
        last = principal_part + principal_part * monthly_rate
        total_interest = monthly_rate * principal_10k * (months + 1) / 2
        total = principal_10k + total_interest
        monthly = total / months
    return {
        "repayment_method": repayment_method,
        "principal_10k": round(principal_10k, 2),
        "annual_rate_pct": annual_rate_pct,
        "years": years,
        "average_monthly_payment_10k": round(monthly, 2),
        "first_month_payment_10k": round(first, 2),
        "last_month_payment_10k": round(last, 2),
        "total_payment_10k": round(total, 2),
        "total_interest_10k": round(total - principal_10k, 2),
    }


def calculate_compound_growth(
    initial_10k: float,
    monthly_contribution_10k: float,
    annual_rate_pct: float,
    years: int,
) -> dict[str, Any]:
    if initial_10k < 0 or monthly_contribution_10k < 0:
        raise ValueError("capital and contribution must be >= 0")
    if annual_rate_pct < 0 or years < 1:
        raise ValueError("rate must be >= 0 and years >= 1")
    months = years * 12
    rate = annual_rate_pct / 100 / 12
    if rate == 0:
        final = initial_10k + monthly_contribution_10k * months
    else:
        growth = (1 + rate) ** months
        final = initial_10k * growth + monthly_contribution_10k * (growth - 1) / rate
    contributed = initial_10k + monthly_contribution_10k * months
    return {
        "final_value_10k": round(final, 2),
        "total_contributed_10k": round(contributed, 2),
        "total_gain_10k": round(final - contributed, 2),
        "annual_rate_pct": annual_rate_pct,
        "years": years,
    }


def calculate_monthly_cashflow(
    monthly_income_10k: float,
    monthly_loan_payment_10k: float,
    monthly_living_cost_10k: float,
    other_monthly_costs_10k: float = 0,
    monthly_rent_income_10k: float = 0,
) -> dict[str, Any]:
    values = [
        monthly_income_10k,
        monthly_loan_payment_10k,
        monthly_living_cost_10k,
        other_monthly_costs_10k,
        monthly_rent_income_10k,
    ]
    if any(value < 0 for value in values):
        raise ValueError("cashflow inputs must be >= 0")
    available = monthly_income_10k + monthly_rent_income_10k
    expenses = monthly_loan_payment_10k + monthly_living_cost_10k + other_monthly_costs_10k
    return {
        "monthly_cashflow_10k": round(available - expenses, 2),
        "monthly_available_income_10k": round(available, 2),
        "monthly_expenses_10k": round(expenses, 2),
        "debt_service_ratio_pct": (
            round(monthly_loan_payment_10k / available * 100, 2) if available else None
        ),
    }
