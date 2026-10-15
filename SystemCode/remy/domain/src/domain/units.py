import math

from .exceptions import DomainError, MissingConversionError, UnitConversionError


# ---------------------------------------------------------------------------
# Fixed unit → gram mapping.
#
# These are ASSUMPTIONS, not measurements. Volumetric units assume a
# water-like density (1 g/ml). Count and container units assume an
# "average" weight that is wrong for specific ingredients (a clove of
# garlic is ~3 g, not 5 g; a can of tomatoes is ~400 g, not 70 g).
#
# The plan API must surface `"UNIT_ASSUMED_GRAMS"` in the response
# warnings whenever this table is used for a non-mass unit, so callers
# know the nutrient totals are estimates.
# ---------------------------------------------------------------------------
_UNIT_TO_GRAMS: dict[str, float] = {
    # ---- Mass (exact) ----------------------------------------------------
    "g": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "pound": 453.592, "pounds": 453.592,

    # ---- Volume (assumes water density) ----------------------------------
    "ml": 1.0, "milliliter": 1.0, "milliliters": 1.0,
    "millilitre": 1.0, "millilitres": 1.0,
    "l": 1000.0, "liter": 1000.0, "liters": 1000.0,
    "litre": 1000.0, "litres": 1000.0,
    "tsp": 5.0, "teaspoon": 5.0, "teaspoons": 5.0,
    "tbsp": 15.0, "tablespoon": 15.0, "tablespoons": 15.0,
    "cup": 240.0, "cups": 240.0,
    "pint": 473.0, "pints": 473.0,
    "quart": 946.0, "quarts": 946.0,
    "gallon": 3785.0, "gallons": 3785.0,

    # ---- Count (assumed average) -----------------------------------------
    "pc": 50.0, "pcs": 50.0, "piece": 50.0, "pieces": 50.0,
    "clove": 5.0, "cloves": 5.0,
    "pinch": 5.0, "pinches": 5.0,
    "dash": 1.0, "dashes": 1.0,
    "slice": 30.0, "slices": 30.0,
    "stalk": 40.0, "stalks": 40.0,
    "head": 300.0, "heads": 300.0,
    "bunch": 100.0, "bunches": 100.0,

    # ---- Containers (assumed average) ------------------------------------
    "can": 70.0, "cans": 70.0,
    "package": 100.0, "packages": 100.0, "pkg": 100.0,
    "jar": 200.0, "jars": 200.0,
    "bottle": 500.0, "bottles": 500.0,
    "box": 200.0, "boxes": 200.0,
    "bag": 250.0, "bags": 250.0,
    "carton": 250.0, "cartons": 250.0,
}

# Units whose gram value is exact (mass). Everything else emits a warning.
_EXACT_UNITS: frozenset[str] = frozenset({
    "g", "gram", "grams",
    "kg", "kilogram", "kilograms",
    "mg", "milligram", "milligrams",
    "oz", "ounce", "ounces",
    "lb", "pound", "pounds",
})


def to_grams(
        quantity: float,
        unit: str,
        *,
        grams_per_tbsp: float | None = None,   # deprecated; ignored
        grams_per_piece: float | None = None,  # deprecated; ignored
        density_g_per_ml: float | None = None, # ignored
) -> tuple[float, list[str]]:
    """Convert a quantity in any known unit to grams.

    Uses a fixed unit → gram table. Mass units are exact. Every other unit
    (volume, count, container) uses an assumed average weight, which is
    nutritionally approximate. The returned warnings flag this so the caller
    can surface it in the API response.

    Parameters
    ----------
    quantity
        Amount to convert. Must be finite and positive.
    unit
        Case- and whitespace-insensitive unit string.
    grams_per_tbsp, grams_per_piece, density_g_per_ml
        Deprecated. Retained so older callers don't break. Ignored.

    Returns
    -------
    (grams, warnings)
        ``warnings`` is empty for exact mass units; otherwise it contains
        ``"UNIT_ASSUMED_GRAMS"``.
    """
    if not math.isfinite(quantity) or quantity <= 0:
        raise DomainError("Quantity must be finite and positive")

    normalised = (unit or "").lower().strip()

    factor = _UNIT_TO_GRAMS.get(normalised)
    if factor is None:
        raise UnitConversionError(f"Unsupported unit: {unit!r}")

    grams = quantity * factor
    if not math.isfinite(grams) or grams <= 0:
        raise DomainError("Converted mass must be finite and positive")

    warnings = [] if normalised in _EXACT_UNITS else ["UNIT_ASSUMED_GRAMS"]
    return grams, warnings
