from dataclasses import dataclass, field
from domain.types import Nutrition


@dataclass
class Ingredient:
    quantity: float | None
    unit: str | None
    text: str | None = None
    preparation: str | None = None
    optional: bool = False
    position: int | None = None
    occurrence_id: str = ""
    raw_text: str | None = None
    cleaned_text: str | None = None
    description: str | None = None
    concept_name: str | None = None
    canonical_key: str | None = None
    ingredients: str | None = None
    allergen_evidence_kinds: list[str] | None = None
    potential_allergens: list[str] | None = None
    may_allergic: bool | None = None
    allergen_screening_status: str | None = None
    halal_status: str | None = None
    halal_evidence_kind: str | None = None
    halal_freshness_status: str | None = None
    vegetarian_status: str | None = None
    vegetarian_evidence_kind: str | None = None
    vegetarian_concerns: list[str] | None = None
    may_non_vegetarian: bool | None = None
    nutrients: Nutrition | None = None
    nutrition_basis: str | None = None
    serving_size: float | None = None
    serving_size_unit: str | None = None


@dataclass
class Recipe:
    recipe_id: str
    title: str
    ingredients: list[Ingredient] = field(default_factory=list)
    nutrients: Nutrition = field(default_factory=dict)
    instructions: str | None = None
    score: float = 0.0
