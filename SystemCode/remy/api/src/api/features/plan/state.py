"""Plain-data encoding of recipes for the LangGraph checkpointer.

Checkpoints are serialized, so graph state holds dicts, not Recipe objects. The
graph nodes decode on the way in and encode on the way out, so the planning code
keeps working with Recipe and Ingredient.
"""
from dataclasses import fields

from .models import Ingredient, Recipe

_INGREDIENT_FIELDS = tuple(f.name for f in fields(Ingredient))


def _encode_ingredient(ingredient) -> dict:
    return {name: getattr(ingredient, name) for name in _INGREDIENT_FIELDS if hasattr(ingredient, name)}


def _decode_ingredient(data: dict) -> Ingredient:
    return Ingredient(**{name: data[name] for name in _INGREDIENT_FIELDS if name in data})


def encode_recipes(recipes) -> list[dict]:
    return [{
        "recipe_id": recipe.recipe_id,
        "title": recipe.title,
        "instructions": getattr(recipe, "instructions", None),
        "nutrients": dict(getattr(recipe, "nutrients", None) or {}),
        "score": getattr(recipe, "score", 0.0),
        "ingredients": [_encode_ingredient(i) for i in getattr(recipe, "ingredients", None) or []],
    } for recipe in recipes]


def decode_recipes(items: list[dict]) -> list[Recipe]:
    recipes = []
    for data in items:
        recipe = Recipe(recipe_id=data["recipe_id"], title=data["title"])
        recipe.instructions = data.get("instructions")
        recipe.nutrients = dict(data.get("nutrients") or {})
        recipe.score = data.get("score", 0.0)
        recipe.ingredients = [_decode_ingredient(i) for i in data.get("ingredients") or []]
        recipes.append(recipe)
    return recipes


def encode_days(days) -> list[list[dict]]:
    return [encode_recipes(day) for day in days]


def decode_days(days) -> list[list[Recipe]]:
    return [decode_recipes(day) for day in days]
