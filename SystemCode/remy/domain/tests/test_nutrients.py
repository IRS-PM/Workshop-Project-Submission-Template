from domain.nutrients import (calculate_portion_nutrients, per_serving,
                               scale_nutrients, sum_nutrients, sum_nutrition)
from domain.types import NutrientProfile


def test_profile_arithmetic_preserves_none():
    first = scale_nutrients(NutrientProfile(protein_g=10, fiber_g=None), 200)
    second = scale_nutrients(NutrientProfile(protein_g=None, fiber_g=3), 100)
    total = sum_nutrients([first, second])
    assert total.protein_g == 20
    assert total.fiber_g == 3
    assert per_serving(total, 2).protein_g == 10


def test_workflow_arithmetic():
    portion = calculate_portion_nutrients(
        nutrition_per_100g={"carbs_g": 20}, quantity_g=200, unit="g", servings=2)
    assert portion["carbs_g"] == 20
    assert sum_nutrition([portion, {"carbs_g": 3}])["carbs_g"] == 23
