import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from .dependencies import get_plan_service
from .graph import build_plan_graph
from .openapi import PLAN_DESCRIPTION, PLAN_RESPONSES
from .schemas import PlanRequest
from .service import PlanService
from .streaming import SSE_HEADERS, stream_plan

router = APIRouter()


@router.post(
    "",
    response_class=StreamingResponse,
    summary="Generate a meal plan (streamed)",
    description=PLAN_DESCRIPTION,
    responses=PLAN_RESPONSES,
)
async def create_plan(
        request: PlanRequest,
        http_request: Request,
        service: PlanService = Depends(get_plan_service)
):
    service.validate(request)
    graph = build_plan_graph(service, http_request.app.state.checkpointer)
    run_id = request.run_id or "run_" + secrets.token_hex(8)
    return StreamingResponse(
        stream_plan(request, service, graph, run_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
