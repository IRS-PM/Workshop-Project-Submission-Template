import pytest

from domain.exceptions import DomainError, UnitConversionError
from domain.units import to_grams


def test_mass_units_are_exact():
    assert to_grams(2, "kg") == (2000.0, [])


def test_volume_and_count_units_use_an_assumed_weight_and_warn():
    assert to_grams(10, "ml") == (10.0, ["UNIT_ASSUMED_GRAMS"])
    assert to_grams(2, "tbsp") == (30.0, ["UNIT_ASSUMED_GRAMS"])
    assert to_grams(1, "pc") == (50.0, ["UNIT_ASSUMED_GRAMS"])


def test_unknown_units_and_non_positive_quantities_are_rejected():
    with pytest.raises(UnitConversionError):
        to_grams(1, "unknown")
    with pytest.raises(DomainError):
        to_grams(0, "g")
