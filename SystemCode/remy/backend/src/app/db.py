from __future__ import annotations

import json

import asyncpg

from app.bloom import BloomFilter


async def create_pool(database_url: str, password: str | None = None) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, password=password, min_size=1, max_size=10)


async def load_bloom(pool: asyncpg.Pool, capacity: int, error_rate: float) -> BloomFilter:
    """Build the filter from every username currently in the table.

    Runs once at startup. The filter lives in process memory, so each worker
    keeps its own copy and rebuilds it on restart - there is nothing to
    invalidate and nothing to keep in sync beyond that.
    """
    bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
    rows = await pool.fetch("SELECT username FROM app_user")
    for row in rows:
        bloom.add(row["username"])
    return bloom


async def user_exists(pool: asyncpg.Pool, username: str) -> bool:
    return await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM app_user WHERE username = $1)", username
    )


async def insert_user(pool: asyncpg.Pool, username: str, password_hash: str) -> None:
    """Raises asyncpg.UniqueViolationError if the username was taken."""
    await pool.execute(
        "INSERT INTO app_user (username, password_hash) VALUES ($1, $2)",
        username,
        password_hash,
    )


async def fetch_password_hash(pool: asyncpg.Pool, username: str) -> str | None:
    return await pool.fetchval(
        "SELECT password_hash FROM app_user WHERE username = $1", username
    )


async def update_password_hash(pool: asyncpg.Pool, username: str, password_hash: str) -> None:
    await pool.execute(
        "UPDATE app_user SET password_hash = $1 WHERE username = $2",
        password_hash,
        username,
    )


async def save_preferences(
    pool: asyncpg.Pool,
    username: str,
    special_diet: str | None,
    cuisines: list[str],
    preferred_nutrient: str | None,
) -> None:
    """Replace this user's preferences outright with a single upsert.

    Cuisines live in one JSONB column as an array (cuisine JSONB in db.sql),
    so the whole preference set is written in one statement - there is no
    child table to keep in sync, and the chosen order is preserved as-is.
    """
    await pool.execute(
        """
        INSERT INTO preference (username, special_diet, cuisine, preferred_nutrient)
        VALUES ($1, $2, $3::jsonb, $4)
        ON CONFLICT (username) DO UPDATE
            SET special_diet = EXCLUDED.special_diet,
                cuisine = EXCLUDED.cuisine,
                preferred_nutrient = EXCLUDED.preferred_nutrient
        """,
        username,
        special_diet,
        json.dumps(cuisines),
        preferred_nutrient,
    )


async def fetch_preferences(pool: asyncpg.Pool, username: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT special_diet, cuisine, preferred_nutrient "
        "FROM preference WHERE username = $1",
        username,
    )
    if row is None:
        return None

    # asyncpg hands jsonb back as raw text, so decode it here; NULL means the
    # user never picked any cuisines and becomes an empty list.
    raw = row["cuisine"]
    cuisines = json.loads(raw) if raw is not None else []
    return {
        "special_diet": row["special_diet"],
        "preferred_nutrient": row["preferred_nutrient"],
        "cuisines": cuisines,
    }


# db.sql only runs when the database is first created, so an older database
# would be missing these tables. Creating them at startup keeps those working.
SAVED_MEAL_DDL = """
CREATE TABLE IF NOT EXISTS saved_meal (
    username   TEXT        NOT NULL
                           REFERENCES app_user (username)
                           ON DELETE CASCADE
                           ON UPDATE CASCADE,
    recipe_id  TEXT        NOT NULL,
    meal       JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (username, recipe_id)
)
"""


MEAL_RATING_DDL = """
CREATE TABLE IF NOT EXISTS meal_rating (
    username  TEXT        NOT NULL
                          REFERENCES app_user (username)
                          ON DELETE CASCADE
                          ON UPDATE CASCADE,
    recipe_id TEXT        NOT NULL,
    liked     BOOLEAN     NOT NULL,
    meal      JSONB       NOT NULL,
    rated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (username, recipe_id)
);

CREATE INDEX IF NOT EXISTS meal_rating_history_idx
    ON meal_rating (username, rated_at DESC);
"""


async def ensure_tables(pool: asyncpg.Pool) -> None:
    await pool.execute(SAVED_MEAL_DDL)
    await pool.execute(MEAL_RATING_DDL)


async def save_meals(pool: asyncpg.Pool, username: str, meals: list[dict]) -> None:
    """Keep each meal, refreshing the stored copy if it was saved before."""
    await pool.executemany(
        """
        INSERT INTO saved_meal (username, recipe_id, meal)
        VALUES ($1, $2, $3::jsonb)
        ON CONFLICT (username, recipe_id) DO UPDATE SET meal = EXCLUDED.meal
        """,
        [(username, meal["recipe_id"], json.dumps(meal)) for meal in meals],
    )


async def fetch_saved_meals(pool: asyncpg.Pool, username: str) -> list[dict]:
    """Newest first, as the Saved page lists them."""
    rows = await pool.fetch(
        "SELECT meal FROM saved_meal WHERE username = $1 ORDER BY created_at DESC",
        username,
    )
    return [json.loads(row["meal"]) for row in rows]


async def delete_saved_meal(pool: asyncpg.Pool, username: str, recipe_id: str) -> bool:
    status = await pool.execute(
        "DELETE FROM saved_meal WHERE username = $1 AND recipe_id = $2",
        username,
        recipe_id,
    )
    return status != "DELETE 0"


async def rate_meal(pool: asyncpg.Pool, username: str, meal: dict, liked: bool) -> dict:
    """Record the like, or change it and date it now if the meal was rated before."""
    row = await pool.fetchrow(
        """
        INSERT INTO meal_rating (username, recipe_id, liked, meal)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (username, recipe_id) DO UPDATE
            SET liked = EXCLUDED.liked, meal = EXCLUDED.meal, rated_at = now()
        RETURNING liked, meal, rated_at
        """,
        username,
        meal["recipe_id"],
        liked,
        json.dumps(meal),
    )
    return _rating(row)


async def fetch_ratings(pool: asyncpg.Pool, username: str) -> list[dict]:
    """The user's history, newest rating first."""
    rows = await pool.fetch(
        "SELECT liked, meal, rated_at FROM meal_rating "
        "WHERE username = $1 ORDER BY rated_at DESC",
        username,
    )
    return [_rating(row) for row in rows]


def _rating(row: asyncpg.Record) -> dict:
    return {"meal": json.loads(row["meal"]), "like": row["liked"], "rated_at": row["rated_at"]}
