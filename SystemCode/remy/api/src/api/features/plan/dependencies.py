from fastapi import Depends, Request
from .repository import PlanRepository
from .service import PlanService


def get_plan_repository(request: Request): return PlanRepository(request.app.state.neo4j_driver)


def get_plan_service(repository=Depends(get_plan_repository)): return PlanService(repository)
