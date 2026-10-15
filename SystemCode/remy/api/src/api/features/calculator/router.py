from fastapi import APIRouter, Depends
from .dependencies import get_calculator_service
from .openapi import CALCULATION_RESPONSES
from .schemas import CostNutritionRequest, CostNutritionResponse
from .service import CostNutritionService

router = APIRouter()


@router.post(
    "/cost-and-nutrition",
    response_model=CostNutritionResponse,
    summary="Calculate cost and nutrition",
    description=(
        "Calculate total and per-serving nutrition for the supplied ingredients, "
        "plus the cost of the amounts consumed and the full retail packages needed (SGD).\n\n"
        "Ingredients are returned in request order. Nutrient values and costs can be `null` "
        "when data is unavailable. Summary costs are `null` if any ingredient lacks pricing. "
        "A successful response may contain `PARTIAL_NUTRITION_DATA` or `MISSING_PACKAGE_DATA` "
        "warnings. Millilitres are treated as grams with an `ML_ASSUMED_GRAMS` warning.\n\n"
        "Use **Try it out** to submit the example request. Calculations require a configured "
        "Neo4j database with food facts and grocery data."
    ),
    responses=CALCULATION_RESPONSES,
)
def calculate_cost_and_nutrition(request: CostNutritionRequest,
                                 service: CostNutritionService = Depends(get_calculator_service)):
    return service.calculate(request)
