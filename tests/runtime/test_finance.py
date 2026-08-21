from kr_apartment_market.services.finance import (
    calculate_compound_growth,
    calculate_loan_payment,
    calculate_monthly_cashflow,
)


def test_zero_rate_loan():
    result = calculate_loan_payment(12000, 0, 1)
    assert result["average_monthly_payment_10k"] == 1000
    assert result["total_interest_10k"] == 0


def test_compound_growth_zero_rate():
    result = calculate_compound_growth(1000, 10, 0, 1)
    assert result["final_value_10k"] == 1120


def test_cashflow():
    result = calculate_monthly_cashflow(500, 150, 200, 20, 50)
    assert result["monthly_cashflow_10k"] == 180
