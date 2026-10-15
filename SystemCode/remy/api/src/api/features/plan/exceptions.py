from api.core.exceptions import AppError


class PlanError(AppError): pass


class UnknownAllergen(PlanError): status_code, code = 400, "UNKNOWN_ALLERGEN"


class UnknownDietary(PlanError): status_code, code = 400, "UNKNOWN_DIETARY"
class UnknownNutrient(PlanError): status_code, code = 400, "UNKNOWN_NUTRIENT"


class NoCandidates(PlanError): status_code, code = 400, "NO_CANDIDATES"


class InvalidNutrientRange(PlanError): status_code, code = 400, "INVALID_NUTRIENT_RANGE"


class PlanInfeasible(PlanError): status_code, code = 400, "PLAN_INFEASIBLE"


class UnsupportedUnit(PlanError): status_code, code = 400, "UNSUPPORTED_UNIT"
