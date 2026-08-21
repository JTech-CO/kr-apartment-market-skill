"""Vendored compatibility financial calculators."""

from __future__ import annotations

from kr_apartment_market.mcp_compat import FastMCP
from kr_apartment_market.services.finance import (
    calculate_compound_growth as _compound,
    calculate_loan_payment as _loan,
    calculate_monthly_cashflow as _cashflow,
)


def register_finance_tools(mcp: FastMCP) -> list[str]:
    names: list[str] = []

    @mcp.tool(name="calculate_loan_payment")
    def calculate_loan_payment(principal_10k: int, annual_rate_pct: float, years: int):
        result = _loan(principal_10k, annual_rate_pct, years, "equal_payment")
        return {
            "monthly_payment_10k": result["average_monthly_payment_10k"],
            "total_payment_10k": result["total_payment_10k"],
            "total_interest_10k": result["total_interest_10k"],
            "principal_10k": principal_10k,
            "annual_rate_pct": annual_rate_pct,
            "years": years,
        }

    names.append("calculate_loan_payment")

    @mcp.tool(name="calculate_compound_growth")
    def calculate_compound_growth(
        initial_10k: int,
        monthly_contribution_10k: float,
        annual_rate_pct: float,
        years: int,
    ):
        return _compound(initial_10k, monthly_contribution_10k, annual_rate_pct, years)

    names.append("calculate_compound_growth")

    @mcp.tool(name="calculate_monthly_cashflow")
    def calculate_monthly_cashflow(
        monthly_income_10k: float,
        monthly_loan_payment_10k: float,
        monthly_living_cost_10k: float,
        other_monthly_costs_10k: float = 0,
    ):
        result = _cashflow(
            monthly_income_10k,
            monthly_loan_payment_10k,
            monthly_living_cost_10k,
            other_monthly_costs_10k,
        )
        return {
            "monthly_cashflow_10k": result["monthly_cashflow_10k"],
            "monthly_income_10k": monthly_income_10k,
            "monthly_loan_payment_10k": monthly_loan_payment_10k,
            "monthly_living_cost_10k": monthly_living_cost_10k,
            "other_monthly_costs_10k": other_monthly_costs_10k,
            "living_cost_auto_applied": False,
        }

    names.append("calculate_monthly_cashflow")
    return names
