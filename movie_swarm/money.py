"""US dollar amounts, compared exactly enough for a film budget."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


_CENTS_OF_A_CENT = Decimal("0.0001")


def as_money(value: float | int | str | Decimal) -> Decimal:
    """Four decimal places, matching the production agent's cost estimates."""
    try:
        amount = Decimal(str(value))
    except Exception as exc:  # Decimal raises several types for bad input
        raise ValueError(f"Not a dollar amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"Not a dollar amount: {value!r}")
    return amount.quantize(_CENTS_OF_A_CENT, rounding=ROUND_HALF_UP)


def money_number(value: float | int | str | Decimal) -> float:
    """A JSON-friendly number rounded to four decimal places."""
    return float(as_money(value))
