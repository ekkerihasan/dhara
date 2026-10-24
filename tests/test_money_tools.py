import pytest

from backend.tools.money import compute_money


@pytest.mark.parametrize("category,inputs,expected", [
    ("deposit_forfeiture", {"deposit": 150000, "on_any_breach": True}, 150000),
    ("deposit_forfeiture", {"deposit": 16000, "on_early_exit": True}, 16000),
    ("deposit_forfeiture", {"deposit": 150000}, 0),
    ("lock_in", {"monthly_rent": 25000, "remaining_months": 6}, 150000),
    ("painting_or_cleaning_fixed", {"amount": 15000}, 15000),
    ("notice_shortfall", {"monthly_rent": 25000, "required_months": 2, "given_months": 1}, 25000),
    ("notice_shortfall", {"monthly_rent": 25000, "required_months": 1, "given_months": 2}, 0),
    ("rent_escalation_excess", {"monthly_rent": 25000, "escalation_percent": 15}, 15000),
    ("rent_escalation_excess", {"monthly_rent": 25000, "escalation_percent": 10}, 0),
    ("rent_escalation_excess", {"monthly_rent": 25000, "escalation_percent": 5}, 0),
    ("painting_or_cleaning_fixed", {"amount": 12.5}, 13),
])
def test_money(category: str, inputs: dict, expected: int) -> None:
    assert compute_money(category, inputs) == expected


@pytest.mark.parametrize("inputs", [{}, {"amount": -1}, {"amount": True}, {"amount": float("inf")}, {"amount": "5000"}])
def test_rejects_invalid_money(inputs: dict) -> None:
    with pytest.raises(ValueError):
        compute_money("painting_or_cleaning_fixed", inputs)


def test_unknown_category_and_invalid_flag() -> None:
    with pytest.raises(ValueError):
        compute_money("guaranteed_legal_award", {})
    with pytest.raises(ValueError):
        compute_money("deposit_forfeiture", {"on_any_breach": "true", "deposit": 1})
