from dataclasses import dataclass
from typing import Literal, TypedDict

NUTRIENT_FIELDS = ("calories_kcal", "protein_g", "fat_g", "saturated_fat_g",
                   "carbs_g", "fiber_g", "sugar_g", "sodium_mg", "cholesterol_mg")


@dataclass(frozen=True)
class NutrientProfile:
    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    saturated_fat_g: float | None = None
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    cholesterol_mg: float | None = None


class Nutrition(TypedDict, total=False):
    calories: float | None
    # calories_kcal: float | None
    protein_g: float | None
    fat_g: float | None
    saturated_fat_g: float | None
    carbs_g: float | None
    fiber_g: float | None
    sugar_g: float | None
    sodium_mg: float | None
    cholesterol_mg: float | None


CheckState = Literal["pass", "fail", "unknown", "not_requested"]
