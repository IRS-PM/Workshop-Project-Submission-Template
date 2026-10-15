"""Jev judge as the last task of the plan graph (after generate).

JUDGE_MODE=jev  (default) grade every candidate in the final pool with a 0 to 3 Score question.
JUDGE_MODE=off  the task does nothing.
                Needs JEV_API_KEY: without it the API refuses to start. A Jev call that fails
                at runtime is logged on the trace and the plan is still returned, because
                the judge only records metrics and must not block a plan.

The judge grades the pool, then the plan's ranking is scored with those grades:
nDCG@3, Precision@3 and pairwise_accuracy. The metrics go to the plan's Langfuse trace.
The judge does not change the plan.

Judge scores are floats from 0 to 3. The metrics need integer grades, so a score is
rounded half up to the nearest integer first.
"""

import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor

from api.core.jev import JevClient, JevConfigError, JevError, require_jev_key, score
from api.core.monitoring import enqueue_trace_scores, observation, update_observation
from .exceptions import PlanError
from .jev_ranking import ranking_version, recipe_state, request_state
from .metrics import ranking_metrics

logger = logging.getLogger(__name__)

JUDGE_MODES = ("off", "jev")
JUDGE_VERSION = "jev-judge-fit-score-v1"
JUDGE_CONCURRENCY = 8
JUDGE_LEVELS = [
    "Unsuitable: does not meet the request's nutrient targets or breaks a restriction",
    "Marginal: meets some targets and clearly misses others",
    "Relevant: meets most targets within reasonable tolerance",
    "Highly relevant: meets all targets closely and respects every restriction",
]
JUDGE_QUESTION = score(
    instructions=(
        "Grade how well this recipe fits the request. Use the request's nutrient targets and "
        "restrictions as they appear in the request. Pick the level that matches the recipe's "
        "nutrients and ingredients."
    ),
    levels=JUDGE_LEVELS,
)


class JudgeUnavailable(PlanError):
    status_code, code = 503, "JUDGE_UNAVAILABLE"


def judge_mode() -> str:
    mode = os.getenv("JUDGE_MODE", "jev").strip().lower()
    if mode not in JUDGE_MODES:
        raise ValueError(f"JUDGE_MODE must be one of {', '.join(JUDGE_MODES)}, got {mode!r}")
    return mode


def validate_judge_config():
    """Called at startup: jev mode without a key must not start."""
    if judge_mode() == "jev":
        require_jev_key()


def judge_one(client: JevClient, request_payload: dict, recipe_payload: dict) -> dict:
    """recipe_payload: recipe_id, title, ingredients (text), nutrients, instructions."""
    state = {"request": request_payload, "recipe": {key: recipe_payload.get(key) for key in
             ("recipe_id", "title", "ingredients", "nutrients", "instructions")}}
    answers = client.ask(state, {"fit": JUDGE_QUESTION})
    answer = answers.get("fit", {})
    value = answer.get("score")
    if not isinstance(value, (int, float)) or not 0 <= value <= 3:
        raise JevError("Jev judge returned no usable fit score")
    return {"score": float(value), "probabilities": answer.get("probabilities", {}), "model": client.model}


def judge_grades(judgments: dict) -> dict[str, int]:
    """Judge scores rounded half up to integer grades 0 to 3."""
    return {recipe_id: min(3, max(0, math.floor(result["score"] + 0.5)))
            for recipe_id, result in judgments.items()}


def judge_metrics(ordered_ids: list[str], judgments: dict) -> dict[str, float | None]:
    """nDCG@3, Precision@3 and pairwise_accuracy of a ranking against judge grades."""
    return ranking_metrics(ordered_ids, judge_grades(judgments))


def judge_candidates(recipes, request) -> tuple[dict, dict]:
    """Grade the final pool in ranked order.

    Returns (judgments, metrics). Judgments map recipe_id to {score, probabilities, model}.
    Both are empty when the judge is off.
    """
    if judge_mode() == "off":
        return {}, {}
    try:
        client = JevClient(require_jev_key())
    except JevConfigError as exc:
        raise JudgeUnavailable(str(exc)) from exc
    with observation("judge-candidates") as span:
        update_observation(span, input={"request": request_state(request),
                                        "candidate_ids": [recipe.recipe_id for recipe in recipes]})
        try:
            with ThreadPoolExecutor(max_workers=JUDGE_CONCURRENCY) as executor:
                results = list(executor.map(
                    lambda recipe: judge_one(client, request_state(request), recipe_state(recipe)), recipes))
        except JevError as exc:
            update_observation(span, level="ERROR", status_message=str(exc))
            logger.warning("Jev judge failed; plan returned without judge metrics: %s", exc)
            return {}, {}
        finally:
            client.close()
        judgments = {recipe.recipe_id: result for recipe, result in zip(recipes, results)}
        metrics = judge_metrics([recipe.recipe_id for recipe in recipes], judgments) if recipes else {}
        update_observation(span, output={"metrics": metrics, "judgments": judgments})
        enqueue_trace_scores(
            getattr(span, "trace_id", None), metrics, source="jev-judge",
            comment="LLM judge (Jev) grades of the ranked pool; not human grades",
            metadata={"judge_version": JUDGE_VERSION, "ranker_version": ranking_version()},
        )
    return judgments, metrics
