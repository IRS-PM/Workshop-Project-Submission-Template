class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class UnitConversionAppError(AppError):
    status_code = 400
    code = "MISSING_UNIT_CONVERSION"


def map_domain_error(error: Exception) -> AppError:
    """Translate domain failures at the HTTP boundary."""
    from domain.exceptions import UnitConversionError

    if isinstance(error, UnitConversionError):
        return UnitConversionAppError(str(error))
    return AppError(str(error))
