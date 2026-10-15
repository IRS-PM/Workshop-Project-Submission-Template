"""Choose the reranker: the nutrient rule (default) or Jev.

RANKER_MODE=rule  nutrient deviation ranking, no external calls.
RANKER_MODE=jev   take the top 2K by the nutrient rule, ask Jev whether each recipe
                  is a good fit for the request, and keep the top K by that probability.

Jev mode has no fallback. Without JEV_API_KEY the API refuses to start, and a failed
Jev call fails the request. A silent switch back to the rule would look like Jev results.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from api.core.jev import JevClient, JevConfigError, JevError, noul, require_jev_key
from .exceptions import PlanError
from .ranking import order_candidates, pool_size, rank_candidates

RANKER_MODES = ("rule", "jev")
JEV_CONCURRENCY = 8
RULE_VERSION = "nutrient-deviation-v1"
JEV_VERSION = "jev-good-fit-noul-v1"

GOOD_FIT = noul(
    instructions=(
        "Is this recipe a good fit for the request? Compare the recipe's nutrients with each "
        "nutrient target in the request. It is a good fit only if every target it has is met "
        "within 25%, and it has no ingredient the request excludes."
    ),
    when_true="Meets every nutrient target in the request within 25%",
    when_false="Misses a nutrient target by more than 25%, or contains an excluded ingredient",
)


class RankerUnavailable(PlanError):
    status_code, code = 503, "RANKER_UNAVAILABLE"


def ranker_mode() -> str:
    mode = os.getenv("RANKER_MODE", "rule").strip().lower()
    if mode not in RANKER_MODES:
        raise ValueError(f"RANKER_MODE must be one of {', '.join(RANKER_MODES)}, got {mode!r}")
    return mode


def ranking_version() -> str:
    return JEV_VERSION if ranker_mode() == "jev" else RULE_VERSION


def validate_ranker_config():
    """Called at startup: jev mode without a key must not start."""
    if ranker_mode() == "jev":
        require_jev_key()


def recipe_state(recipe) -> dict:
    return {
        "recipe_id": recipe.recipe_id,
        "title": recipe.title,
        "ingredients": [
            ingredient.cleaned_text or ingredient.raw_text or ingredient.text
            or ingredient.description or ingredient.canonical_key
            for ingredient in recipe.ingredients
        ],
        "nutrients": dict(recipe.nutrients or {}),
        "instructions": recipe.instructions,
    }


def request_state(request) -> dict:
    return request.model_dump(mode="json", exclude={"run_id"})


def good_fit_probability(client: JevClient, recipe, request) -> float:
    answers = client.ask({"request": request_state(request), "recipe": recipe_state(recipe)},
                         {"good_fit": GOOD_FIT})
    answer = answers.get("good_fit", {})
    probability = answer.get("noul")
    if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
        raise JevError("Jev returned no usable good_fit probability")
    return float(probability)


def jev_rerank(recipes, request, client: JevClient) -> list:
    k = pool_size(request)
    ordered = order_candidates(recipes, request)
    pool = ordered[: 2 * k]
    with ThreadPoolExecutor(max_workers=JEV_CONCURRENCY) as executor:
        probabilities = list(executor.map(lambda r: good_fit_probability(client, r, request), pool))
    position = {recipe.recipe_id: index for index, recipe in enumerate(pool)}
    for recipe, probability in zip(pool, probabilities):
        recipe.score = probability
    ranked = sorted(pool, key=lambda r: (-r.score, position[r.recipe_id]))
    return ranked[:k]


def rank_with_mode(recipes, request):
    if ranker_mode() == "rule":
        return rank_candidates(recipes, request)
    try:
        client = JevClient(require_jev_key())
    except JevConfigError as exc:
        raise RankerUnavailable(str(exc)) from exc
    try:
        return jev_rerank(recipes, request, client)
    except JevError as exc:
        raise RankerUnavailable(str(exc)) from exc
    finally:
        client.close()
