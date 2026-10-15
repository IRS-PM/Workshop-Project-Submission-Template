from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app import db
from app.schemas import PreferencesIn, PreferencesOut

router = APIRouter(prefix="/preferences", tags=["preferences"])

# No path is public here, so the JWT middleware has already validated the token
# and left its subject on request.state.username. That is the account these
# endpoints act on - a user cannot read or write anyone else's preferences,
# because the username never comes from the request body.


@router.post("", response_model=PreferencesOut, status_code=status.HTTP_201_CREATED)
async def create(body: PreferencesIn, request: Request) -> PreferencesOut:
    """Store the answers from the cold start, straight after sign up.

    The session cookie set by /auth/signup is what authenticates this call, so
    the preferences land on the account that was just created. An upsert, so a
    retried request (or someone rerunning the wizard) does not fail.
    """
    return await save(body, request)


@router.put("", response_model=PreferencesOut)
async def save(body: PreferencesIn, request: Request) -> PreferencesOut:
    """Replace the whole preference set from the preferences page."""
    username = request.state.username
    await db.save_preferences(
        request.app.state.pool,
        username,
        body.special_diet,
        body.cuisines,
        body.preferred_nutrient,
    )
    return PreferencesOut(username=username, **body.model_dump())


@router.get("", response_model=PreferencesOut)
async def read(request: Request) -> PreferencesOut:
    username = request.state.username
    stored = await db.fetch_preferences(request.app.state.pool, username)
    if stored is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No preferences saved yet.",
        )
    return PreferencesOut(username=username, **stored)
