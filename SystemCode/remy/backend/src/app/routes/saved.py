from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app import db
from app.schemas import SavedMeal, SavedMealsIn

router = APIRouter(prefix="/saved", tags=["saved"])

# Like /preferences, every path here is behind the JWT middleware and acts on
# request.state.username, never on a username from the request.


@router.get("", response_model=list[SavedMeal])
async def list_saved(request: Request) -> list[dict]:
    return await db.fetch_saved_meals(request.app.state.pool, request.state.username)


@router.post("", response_model=list[SavedMeal], status_code=status.HTTP_201_CREATED)
async def save(body: SavedMealsIn, request: Request) -> list[dict]:
    """Keep the meals picked on the home page. Saving one twice is not an error."""
    pool = request.app.state.pool
    username = request.state.username
    await db.save_meals(pool, username, [meal.model_dump() for meal in body.meals])
    return await db.fetch_saved_meals(pool, username)


@router.delete("/{recipe_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(recipe_id: str, request: Request) -> None:
    removed = await db.delete_saved_meal(
        request.app.state.pool, request.state.username, recipe_id
    )
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="That meal is not saved.")
