from fastapi import Depends, Request
from .repository import CostNutritionRepository
from .service import CostNutritionService


def get_calculator_repository(request: Request) -> CostNutritionRepository:
    return CostNutritionRepository(request.app.state.neo4j_driver)


def get_calculator_service(repository: CostNutritionRepository = Depends(get_calculator_repository)) -> CostNutritionService:
    return CostNutritionService(repository)
