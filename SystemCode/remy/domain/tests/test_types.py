from dataclasses import fields

from domain.types import CheckState, NUTRIENT_FIELDS, NutrientProfile


def test_profile_and_shared_vocabulary():
    assert NutrientProfile(protein_g=2).protein_g == 2
    assert len(NUTRIENT_FIELDS) == 9
    assert CheckState


def test_nutrient_fields_match_the_profile():
    assert set(NUTRIENT_FIELDS) == {field.name for field in fields(NutrientProfile)}
