from api.features.calculator.domain.nutrition import per_serving, scale_nutrients, sum_nutrients
from api.features.calculator.models import NutrientProfile


def test_scaling_preserves_nulls_and_sums_values():
    first = scale_nutrients(NutrientProfile(protein_g=10, fiber_g=None), 200)
    second = scale_nutrients(NutrientProfile(protein_g=None, fiber_g=3), 100)
    total = sum_nutrients([first, second])
    assert total.protein_g == 20
    assert total.fiber_g == 3
    assert per_serving(total, 2).protein_g == 10
