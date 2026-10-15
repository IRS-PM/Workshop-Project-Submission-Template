from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app import db
from app.schemas import RatingIn, RatingOut

router = APIRouter(prefix="/ratings", tags=["ratings"])

# Behind the JWT middleware like /saved: every call acts on
# request.state.username, never on a username from the request.


@router.get("", response_model=list[RatingOut])
async def history(request: Request) -> list[dict]:
    """Every meal the user liked or did not, newest first."""
    return await db.fetch_ratings(request.app.state.pool, request.state.username)


@router.put("/{recipe_id:path}", response_model=RatingOut)
async def rate(recipe_id: str, body: RatingIn, request: Request) -> dict:
    if body.meal.recipe_id != recipe_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The meal in the body is not the one in the path.",
        )
    return await db.rate_meal(
        request.app.state.pool, request.state.username, body.meal.model_dump(), body.like
    )
