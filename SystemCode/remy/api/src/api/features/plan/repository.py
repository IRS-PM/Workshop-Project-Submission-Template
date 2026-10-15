"""Repository adapter for plan candidates.

Uses :BEST_FULFILLMENT materialization for fast reads.
Run scripts/rebuild_best_fulfillment.py after each data prep cycle.
"""
import time
from typing import Optional

from domain import Nutrition
from .models import Ingredient, Recipe

# ---------------------------------------------------------------------------
# Runtime query — reads pre-computed :BEST_FULFILLMENT edges.
#
# No sort, no head(collect()), no fan-out over all FULFILLS candidates.
# Single hop: (FoodConcept)-[:BEST_FULFILLMENT]->(Food)
#
# The second OPTIONAL MATCH reuses the SAME `f` variable, so it only
# traverses FULFILLS edges ending at the winning food (cheap).
#
# Requirements:
#   - Index: :Recipe(recipe_id)
#   - Index: :FoodConcept(canonical_key)
#   - Materialization: scripts/rebuild_best_fulfillment.py
# ---------------------------------------------------------------------------
QUERY = """
MATCH (r:Recipe)
WHERE r.recipe_id IS NOT NULL
WITH r
ORDER BY r.recipe_id
LIMIT $limit

MATCH (r)-[req:REQUIRES]->(fc:FoodConcept)
OPTIONAL MATCH (fc)-[best:BEST_FULFILLMENT]->(f:Food)

WITH r, collect({
  quantity: req.quantity, unit: req.unit, optional: req.optional,
  preparation: req.preparation, raw_text: req.raw_text,
  cleaned_text: req.cleaned_text,
  occurrence_id: req.occurrence_id, position: req.position,
  canonical_key: fc.canonical_key, concept_name: fc.name,
  description: f.description, ingredients: f.ingredients,
  serving_size: f.serving_size, serving_size_unit: f.serving_size_unit,
  nutrition_basis: f.nutrition_basis, energy_kcal: f.energy_kcal,
  protein_g: f.protein_g, fat_g: f.fat_g, saturated_fat_g: f.saturated_fat_g,
  carbohydrate_g: f.carbohydrate_g, fiber_g: f.fiber_g, sugars_g: f.sugars_g,
  sodium_mg: f.sodium_mg, cholesterol_mg: f.cholesterol_mg,
  vegetarian_status: best.vegetarian_status,
  vegetarian_evidence_kind: best.vegetarian_evidence_kind,
  vegetarian_concerns: best.vegetarian_concerns,
  may_non_vegetarian: best.may_non_vegetarian,
  halal_status: best.halal_status,
  halal_evidence_kind: best.halal_evidence_kind,
  halal_freshness_status: best.halal_freshness_status,
  allergen_evidence_kinds: best.allergen_evidence_kinds,
  potential_allergens: best.potential_allergens,
  may_allergic: best.may_allergic,
  allergen_screening_status: best.allergen_screening_status
}) AS ingredients

RETURN r.recipe_id AS recipe_id,
       r.Title AS title,
       r.Instructions AS instructions,
       ingredients
ORDER BY recipe_id
"""

def _build_nutrients(x: dict) -> Nutrition:
    return {
        "calories": x.get("energy_kcal"),
        "protein_g": x.get("protein_g"),
        "fat_g": x.get("fat_g"),
        "saturated_fat_g": x.get("saturated_fat_g"),
        "carbs_g": x.get("carbohydrate_g"),
        "fiber_g": x.get("fiber_g"),
        "sugar_g": x.get("sugars_g"),
        "sodium_mg": x.get("sodium_mg"),
        "cholesterol_mg": x.get("cholesterol_mg"),
    }


def _fallback_text(x: dict) -> Optional[str]:
    return (
            x.get("cleaned_text")
            or x.get("raw_text")
            or x.get("description")
            or x.get("concept_name")
            or x.get("canonical_key")
    )


def _build_ingredient(x: dict) -> Ingredient:
    """Construct Ingredient without Pydantic validation overhead (fast path)."""
    ing = Ingredient.__new__(Ingredient)
    ing.quantity = x.get("quantity")
    ing.unit = x.get("unit")
    ing.text = _fallback_text(x)
    ing.preparation = x.get("preparation")
    ing.optional = bool(x.get("optional", False))
    ing.position = x.get("position")
    ing.occurrence_id = x.get("occurrence_id")
    ing.raw_text = x.get("raw_text")
    ing.cleaned_text = x.get("cleaned_text")
    ing.description = x.get("description")
    ing.concept_name = x.get("concept_name")
    ing.canonical_key = x.get("canonical_key")
    ing.ingredients = x.get("ingredients")
    ing.allergen_evidence_kinds = x.get("allergen_evidence_kinds")
    ing.potential_allergens = x.get("potential_allergens")
    ing.may_allergic = x.get("may_allergic")
    ing.allergen_screening_status = x.get("allergen_screening_status")
    ing.halal_status = x.get("halal_status")
    ing.halal_evidence_kind = x.get("halal_evidence_kind")
    ing.halal_freshness_status = x.get("halal_freshness_status")
    ing.vegetarian_status = x.get("vegetarian_status")
    ing.vegetarian_evidence_kind = x.get("vegetarian_evidence_kind")
    ing.vegetarian_concerns = x.get("vegetarian_concerns")
    ing.may_non_vegetarian = x.get("may_non_vegetarian")
    ing.nutrients = _build_nutrients(x)
    ing.nutrition_basis = x.get("nutrition_basis")
    ing.serving_size = x.get("serving_size")
    ing.serving_size_unit = x.get("serving_size_unit")
    return ing


def _build_recipe(row: dict) -> Optional[Recipe]:
    ingredients_raw = row.get("ingredients") or []

    quantifiable = [
        x for x in ingredients_raw if (x.get("quantity") or 0) != 0
    ]
    if not quantifiable:
        return None

    recipe_id = str(row["recipe_id"])
    recipe = Recipe.__new__(Recipe)
    recipe.recipe_id = recipe_id
    recipe.title = row.get("title") or recipe_id
    recipe.instructions = row.get("instructions")
    recipe.ingredients = [_build_ingredient(x) for x in quantifiable]
    return recipe


class PlanRepository:
    def __init__(self, driver):
        self.driver = driver

    def fetch_candidates(self, limit: int = 1000) -> list[Recipe]:
        t0 = time.perf_counter()

        with self.driver.session() as session:
            rows = list(session.run(QUERY, limit=limit))

        t1 = time.perf_counter()

        result = [
            r for r in (_build_recipe(row) for row in rows) if r is not None
        ]

        t2 = time.perf_counter()
        print(
            f"fetch_candidates: neo4j={(t1-t0)*1000:.0f}ms "
            f"python={(t2-t1)*1000:.0f}ms "
            f"total={(t2-t0)*1000:.0f}ms "
            f"recipes={len(result)}"
        )
        return result
