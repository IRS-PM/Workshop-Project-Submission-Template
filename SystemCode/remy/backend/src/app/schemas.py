from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Same shape the database enforces in app_user_username_format, so a bad
# username is rejected at the edge with a useful message instead of coming back
# as a constraint violation.
USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,31}$"


class UsernameIn(BaseModel):
    """A request carrying just a username, e.g. the availability check."""

    username: str = Field(min_length=3, max_length=32)

    @field_validator("username")
    @classmethod
    def normalise_username(cls, value: str) -> str:
        """Lowercase before validating, so Alice and alice are one account."""
        lowered = value.strip().lower()
        if not re.fullmatch(USERNAME_PATTERN, lowered):
            raise ValueError(
                "username must be 3-32 characters of letters, digits, dot, "
                "dash or underscore, and start with a letter or digit"
            )
        return lowered


class Credentials(UsernameIn):
    password: str = Field(min_length=8, max_length=1024)


class AccountOut(BaseModel):
    username: str


class AvailabilityOut(BaseModel):
    username: str
    available: bool
    # True when the filter alone settled it, i.e. no database round trip was
    # needed. Useful for seeing the filter earn its keep.
    answered_by_filter: bool


class SessionOut(BaseModel):
    """What sign up and sign in return.

    No token here on purpose - it is set as an HttpOnly cookie, which the
    browser stores and replays but JavaScript cannot read. Putting a copy in
    the body would hand it straight back to any script on the page.
    """

    username: str
    expires_at: int  # unix seconds


class RefreshOut(BaseModel):
    expires_at: int
    # False when the presented token still had plenty of life and was handed
    # straight back, so a client can call refresh on every app open cheaply.
    refreshed: bool


# Mirrors the preference_special_diet_known CHECK in db.sql.
Diet = Literal["halal", "vegetarian", "meat"]


class PreferencesIn(BaseModel):
    """What the cold start collects. Every field is optional: the wizard lets
    the user skip cuisines and nutrient, and skip the whole thing entirely."""

    special_diet: Diet | None = None
    cuisines: list[str] = Field(default_factory=list, max_length=40)
    preferred_nutrient: str | None = Field(default=None, max_length=64)

    @field_validator("cuisines")
    @classmethod
    def clean_cuisines(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks, de-duplicate, keep the order chosen.

        De-duplication is why we do not accept duplicates in the payload: the
        list is stored as one JSONB array and read back verbatim, so repeats
        would surface to the user rather than collapse silently.
        """
        seen: set[str] = set()
        cleaned: list[str] = []
        for raw in value:
            cuisine = raw.strip()
            if not cuisine or len(cuisine) > 64:
                continue
            key = cuisine.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(cuisine)
        return cleaned


class PreferencesOut(PreferencesIn):
    username: str


class SavedMeal(BaseModel):
    """One meal as the planner returned it. Only the id and title are checked;
    the rest (nutrients, ingredients, method) is stored as-is for display."""

    model_config = ConfigDict(extra="allow")

    recipe_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=300)


class SavedMealsIn(BaseModel):
    meals: list[SavedMeal] = Field(min_length=1, max_length=50)


class RatingIn(BaseModel):
    like: bool
    meal: SavedMeal


class RatingOut(BaseModel):
    """One History row: the meal, whether it was liked, and when."""

    meal: SavedMeal
    like: bool
    rated_at: datetime
