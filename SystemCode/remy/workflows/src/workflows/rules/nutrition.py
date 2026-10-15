"""Portion-level nutrient calculations.

Nutrients are stored per 100 g on ``NODE_FOOD``.  This module converts
them to per-serving values given a required quantity in compatible units
and checks carbohydrate range bounds.
"""

from __future__ import annotations

from domain.types import CheckState



# ---------------------------------------------------------------------------
# Carbohydrate range check
# ---------------------------------------------------------------------------


def check_carbs_compliance(
    *,
    carbs_g_per_serving: float | None,
    carbs_g_min: float | None,
    carbs_g_max: float | None,
) -> CheckState:
    """Check carbohydrate per serving against user bounds.

    Returns
    -------
    CheckState
        ``"pass"`` — within bounds.
        ``"fail"`` — outside bounds.
        ``"unknown"`` — missing nutrition or no bounds requested.
        ``"not_requested"`` — no carb bounds were set.
    """
    if carbs_g_min is None and carbs_g_max is None:
        return "not_requested"

    if carbs_g_per_serving is None:
        return "unknown"

    if carbs_g_min is not None and carbs_g_per_serving < carbs_g_min:
        return "fail"

    if carbs_g_max is not None and carbs_g_per_serving > carbs_g_max:
        return "fail"

    return "pass"
