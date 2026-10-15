from dataclasses import asdict

from .types import NUTRIENT_FIELDS, NutrientProfile, Nutrition
from .units import to_grams


def scale_nutrients(profile: NutrientProfile, grams: float) -> NutrientProfile:
    return NutrientProfile(**{
        key: (value * grams / 100.0 if value is not None else None)
        for key, value in asdict(profile).items()
    })


def sum_nutrients(items: list[NutrientProfile]) -> NutrientProfile:
    return NutrientProfile(**{
        key: (sum(v for v in (getattr(item, key) for item in items) if v is not None)
              if any(getattr(item, key) is not None for item in items) else None)
        for key in NUTRIENT_FIELDS
    })


def per_serving(profile: NutrientProfile, servings: int) -> NutrientProfile:
    return NutrientProfile(**{
        key: (value / servings if value is not None else None)
        for key, value in profile.__dict__.items()
    })


def calculate_portion_nutrients(*, nutrition_per_100g: Nutrition | None,
                                quantity_g: float,
                                unit: str,
                                servings: int = 1
                                ) -> Nutrition | None:
    if nutrition_per_100g is None:
        return None
    if unit in {'kcal'}:
        grams = quantity_g
    else:
        try:
            grams, _ = to_grams(quantity_g, unit)
        except Exception:
            return None
    factor = grams / (100.0 * max(servings, 1))

    def scale(value: float | None) -> float | None:
        return round(value * factor, 4) if value is not None else None

    return {key: scale(value) for key, value in nutrition_per_100g.items()
            if value is not None}


def sum_nutrition(servings: list[Nutrition]) -> Nutrition:
    keys = ("calories", "protein_g", "fat_g", "saturated_fat_g", "carbs_g",
            "fiber_g", "sugar_g", "sodium_mg", "cholesterol_mg")
    result: Nutrition = {key: None for key in keys}
    for serving in servings:
        for key in keys:
            value = serving.get(key)
            if value is not None:
                result[key] = value if result[key] is None else round(result[key] + value, 4)
    return result
