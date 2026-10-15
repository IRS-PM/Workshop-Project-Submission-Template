class DomainError(Exception):
    """Base exception for invalid pure-domain input."""


class UnitConversionError(DomainError):
    """A quantity cannot be converted to grams."""


class MissingConversionError(UnitConversionError):
    """A required ingredient-specific conversion is missing or invalid."""
