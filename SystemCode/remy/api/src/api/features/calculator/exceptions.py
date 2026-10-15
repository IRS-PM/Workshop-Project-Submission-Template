from api.core.exceptions import AppError


class UnresolvableIngredient(AppError):
    status_code, code = 400, "UNRESOLVABLE_INGREDIENT"


class AmbiguousIngredient(AppError):
    status_code, code = 400, "AMBIGUOUS_INGREDIENT"


class MissingUnitConversion(AppError):
    status_code, code = 400, "MISSING_UNIT_CONVERSION"


class InvalidPackageData(AppError):
    status_code, code = 200, "INVALID_PACKAGE_DATA"


# Backwards-compatible explicit names used in the written API plan.
UnresolvableIngredientError = UnresolvableIngredient
AmbiguousIngredientError = AmbiguousIngredient
MissingUnitConversionError = MissingUnitConversion
InvalidPackageDataError = InvalidPackageData
