"""Deprecated calculator compatibility shim; use :mod:`domain.units`."""

from domain.exceptions import DomainError, MissingConversionError
from domain.units import to_grams as _to_grams
from api.core.exceptions import UnitConversionAppError


def to_grams(*args, **kwargs):
    """Deprecated compatibility wrapper; use :func:`domain.units.to_grams`."""
    try:
        return _to_grams(*args, **kwargs)
    except MissingConversionError as exc:
        from ..exceptions import MissingUnitConversion
        raise MissingUnitConversion(str(exc)) from exc
    except DomainError as exc:
        raise UnitConversionAppError(str(exc)) from exc
