import logging
import os
import secrets

from workflows.rules.allergen import resolve_allergen_key
from api.core.monitoring import observation, update_observation
from .evaluation import save_evaluation
from .filtering import filter_candidates, SUPPORTED_NUTRIENTS
from .jev_ranking import rank_with_mode, ranking_version
from .repository import PlanRepository
from .solver_v2 import solve_v2
from .aggregation import aggregate
from .schemas import PlanResponse, DayResponse, MealResponse, MealIngredientResponse
from .exceptions import InvalidNutrientRange, UnknownAllergen, UnknownDietary, UnknownNutrient
from .state import encode_days, encode_recipes

logger = logging.getLogger(__name__)
SUPPORTED_DIETARY = {"halal", "vegetarian"}


def trace_plan(request):
    return observation(
        "meal-plan", horizon_days=getattr(request, "horizon_days", None),
        meals_per_day=getattr(request, "meals_per_day", None),
        servings=getattr(request, "servings", None),
        constraint_counts={name: len(getattr(request, name, None) or [])
                           for name in ("allergies", "dietary", "nutrients")},
        ranking_version=ranking_version(),
        data_version=os.getenv("REMY_DATA_VERSION", "unspecified"),
    )


def complete_plan(response, request, recipes, span):
    response.trace_id = span.trace_id if span is not None else None
    try:
        response.evaluation_id = save_evaluation(response.trace_id, response.plan_id, request, recipes)
    except Exception:
        logger.warning("Ranking snapshot storage failed; meal plan remains available")
    update_observation(span, output=response.model_dump(mode="json"))
    return response


def dump(obj):
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj


class PlanService:
    def __init__(self, repository: PlanRepository):
        self.repository = repository

    def validate(self, request):
        for n in request.nutrients or []:
            if n.code not in SUPPORTED_NUTRIENTS:
                raise UnknownNutrient(f"Unknown nutrient: {n.code}")
            if n.limit and n.limit.min is not None and n.limit.max is not None and n.limit.min > n.limit.max:
                raise InvalidNutrientRange("min cannot exceed max")
        for a in request.allergies or []:
            if resolve_allergen_key(a.code) is None:
                raise UnknownAllergen(f"Unknown allergen: {a.code}")
        for d in request.dietary or []:
            if d.code not in SUPPORTED_DIETARY:
                raise UnknownDietary(f"Unknown dietary code: {d.code}")

    def fetch_candidates(self, request=None):
        with observation("retrieve-candidates") as span:
            update_observation(span, input={"request": dump(request)})
            recipes = self.repository.fetch_candidates()
            update_observation(span, output=encode_recipes(recipes))
            return recipes

    def filter_stage(self, recipes, request):
        with observation("filter-candidates") as span:
            update_observation(span, input={"request": dump(request), "recipes": encode_recipes(recipes)})
            filtered = filter_candidates(recipes, request)
            update_observation(span, output=encode_recipes(filtered))
            return filtered

    def rank_stage(self, filtered, request):
        with observation("rank-candidates") as span:
            update_observation(span, input={"request": dump(request), "recipes": encode_recipes(filtered)})
            ranked = rank_with_mode(filtered, request)
            update_observation(span, output=encode_recipes(ranked))
            return ranked

    def select_candidates(self, recipes, request):
        return self.rank_stage(self.filter_stage(recipes, request), request)

    def solve(self, recipes, request):
        with observation("solve-plan") as span:
            update_observation(span, input={"request": dump(request), "candidates": encode_recipes(recipes)})
            days, relaxations = solve_v2(recipes, request)
            update_observation(span, output={"days": encode_days(days), "relaxations": relaxations})
            return days, relaxations

    def build_response(self, days, relaxations, request):
        with observation("generate-response") as span:
            update_observation(span, input={
                "request": dump(request), "days": encode_days(days), "relaxations": relaxations,
            })
            response_days = []
            for d, meals in enumerate(days, 1):
                response_days.append(DayResponse(day=d, meals=[
                    MealResponse(
                        slot=f"meal_{i}",
                        recipe_id=r.recipe_id,
                        title=r.title,
                        nutrients={
                            k: round((v or 0) * request.servings, 2) for k, v in
                            r.nutrients.items() if v is not None
                        },
                        ingredients=[MealIngredientResponse(
                            quantity=None if ing.quantity is None else round(ing.quantity * request.servings, 2),
                            unit=ing.unit,
                            text=ing.cleaned_text or ing.raw_text or ing.description or ing.canonical_key,
                            preparation=ing.preparation,
                            optional=bool(ing.optional),
                        ) for ing in sorted(r.ingredients, key=lambda ing: (
                            ing.position if ing.position is not None else 0, ing.occurrence_id or ""))],
                        instructions=r.instructions,
                    ) for i, r in enumerate(meals, 1)
                ]))
            response = PlanResponse(plan_id="plan_" + secrets.token_hex(5),
                                status="partial" if relaxations or request.allergies or request.dietary else "complete",
                                message=f"Successfully generated a {request.horizon_days}-day meal plan.",
                                validation_summary={
                                    "allergen_status": "unverified" if request.allergies else "not_requested",
                                    "dietary_status": "unverified" if request.dietary else "not_requested"},
                                relaxations=relaxations, horizon_totals=aggregate(days, request),
                                days=response_days)
            update_observation(span, output=response.model_dump(mode="json"))
            return response

    def generate(self, request):
        with trace_plan(request) as span:
            self.validate(request)
            recipes = self.select_candidates(self.fetch_candidates(), request)
            days, relaxations = self.solve(recipes, request)
            return complete_plan(self.build_response(days, relaxations, request), request, recipes, span)
