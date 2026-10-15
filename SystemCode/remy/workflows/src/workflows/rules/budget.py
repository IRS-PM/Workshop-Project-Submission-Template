"""Budget and cost calculations.

Distinguishes between consumed cost (portion used in the recipe) and
whole-package purchase cost.  Only calculates when ingredient and package
units share a compatible mass base.
"""

from __future__ import annotations

from domain.types import CheckState

# ---------------------------------------------------------------------------
# Unit-conversion helpers (mass only — volume/count are incompatible)
# ---------------------------------------------------------------------------

_TO_GRAMS: dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "mg": 0.001,
    "milligram": 0.001,
    "milligrams": 0.001,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}


def _to_grams(quantity: float, unit: str) -> float | None:
    """Convert *quantity* in *unit* to grams, or ``None`` if unsupported."""
    factor = _TO_GRAMS.get(unit.lower().strip())
    if factor is None:
        return None
    return quantity * factor


# ---------------------------------------------------------------------------
# Cost calculations
# ---------------------------------------------------------------------------


def compute_consumed_cost(
    *,
    ingredient_quantity: float,
    ingredient_unit: str,
    pack_price_sgd: float | None,
    pack_size_g: float | None,
) -> float | None:
    """Calculate the consumed portion cost in SGD.

    Returns ``None`` when price, package size, or unit conversion is
    unavailable (incompatible units).
    """
    if pack_price_sgd is None or pack_size_g is None:
        return None
    if pack_size_g <= 0:
        return None

    grams_needed = _to_grams(ingredient_quantity, ingredient_unit)
    if grams_needed is None:
        return None

    return round(pack_price_sgd * (grams_needed / pack_size_g), 4)


def compute_whole_package_cost(
    *,
    pack_price_sgd: float | None,
) -> float | None:
    """Return the whole-package cost, or ``None`` if unavailable."""
    return pack_price_sgd


def calculate_food_cost(
    *,
    price_sgd: float | None,
    pack_size_g: float | None,
    req_quantity: float,
    req_unit: str,
) -> tuple[float | None, float | None]:
    """Calculate both consumed portion cost and whole-package cost.

    Returns a tuple (consumed_cost_sgd, whole_package_cost_sgd). Each element
    may be ``None`` if the relevant data or unit compatibility is missing.
    """
    consumed = compute_consumed_cost(
        ingredient_quantity=req_quantity,
        ingredient_unit=req_unit,
        pack_price_sgd=price_sgd,
        pack_size_g=pack_size_g,
    )
    package = compute_whole_package_cost(pack_price_sgd=price_sgd)
    return consumed, package


# ---------------------------------------------------------------------------
# Budget check
# ---------------------------------------------------------------------------


def check_budget_compliance(
    *,
    cost_sgd: float | None,
    budget_sgd: float | None,
    budget_period: str | None,
) -> CheckState:
    """Check total consumed cost against the user's budget.

    For ``budget_period="meal"``, compare consumed cost directly.
    For ``budget_period="day"``, the result is ``Partial`` unless all
    daily meals are represented (which this single-recipe check cannot
    determine), so we return ``"pass"`` only if consumed cost is within
    budget and note the limitation.

    Returns
    -------
    CheckState
        ``"pass"`` — within budget.
        ``"fail"`` — exceeds budget.
        ``"unknown"`` — cannot compute (missing data or incompatible units).
        ``"not_requested"`` — no budget constraint was set.
    """
    if budget_sgd is None or budget_period is None:
        return "not_requested"

    if cost_sgd is None:
        return "unknown"

    if cost_sgd <= budget_sgd:
        return "pass"

    return "fail"
