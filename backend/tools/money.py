"""Deterministic exposure estimates; these are not awards or legal caps."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def _number(inputs: dict[str, Any], key: str) -> Decimal:
    value = inputs.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{key} must be a non-negative number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid {key}") from exc
    if not number.is_finite() or number < 0 or number > Decimal("1e12"):
        raise ValueError(f"{key} must be finite and between zero and 1e12")
    return number


def compute_money(finding_type: str, inputs: dict[str, Any]) -> int:
    """Calculate INR exposure, rounding fractional rupees half up once at the end."""
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    if finding_type == "deposit_forfeiture":
        flags = [inputs.get(key, False) for key in ("on_any_breach", "on_early_exit")]
        if not all(isinstance(flag, bool) for flag in flags):
            raise ValueError("Forfeiture flags must be booleans")
        amount = _number(inputs, "deposit") if any(flags) else Decimal(0)
    elif finding_type == "lock_in":
        amount = _number(inputs, "monthly_rent") * _number(inputs, "remaining_months")
    elif finding_type == "painting_or_cleaning_fixed":
        amount = _number(inputs, "amount")
    elif finding_type == "notice_shortfall":
        months = max(Decimal(0), _number(inputs, "required_months") - _number(inputs, "given_months"))
        amount = _number(inputs, "monthly_rent") * months
    elif finding_type == "rent_escalation_excess":
        excess = max(Decimal(0), _number(inputs, "escalation_percent") - 10)
        amount = excess * _number(inputs, "monthly_rent") * 12 / 100
    else:
        raise ValueError("Unsupported money category")
    logged = {key: value for key, value in inputs.items()
              if key in {"deposit", "on_any_breach", "on_early_exit", "monthly_rent", "remaining_months",
                         "amount", "required_months", "given_months", "escalation_percent"}
              and isinstance(value, (int, float, Decimal))}
    LOGGER.info("compute_money type=%s inputs=%s", finding_type, str(logged)[:200])
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
