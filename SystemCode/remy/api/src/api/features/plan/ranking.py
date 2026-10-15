from api.features.plan.models import Recipe


def order_candidates(recipes, request) -> list[Recipe]:
    """Rank recipes by how well they fit the request's nutrient targets.

    Each recipe is scored against a per-meal target derived from the request's
    nutrient goals (or limit midpoints when no goal is given). The score is a
    negative sum of normalised deviations, so higher is better. The list is
    returned sorted by descending score, then ascending ``recipe_id``.
    """

    # ------------------------------------------------------------------
    # Step 1: derive a single target value per requested nutrient.
    #
    # Preference order:
    #   1. Explicit goal value, if the request provided one.
    #   2. Midpoint of [min, max], if BOTH bounds are present.
    #   3. Otherwise, None — the nutrient is skipped for ranking.
    #
    # A nutrient with only `min` or only `max` (and no goal) is deliberately
    # skipped: there is no well-defined centre to score against. The solver
    # still enforces the one-sided bound as a hard constraint; ranking simply
    # has no opinion about it.
    # ------------------------------------------------------------------
    targets = {
        n.code: (
            n.goal.value
            if n.goal
            else (
                (n.limit.min + n.limit.max) / 2
                if n.limit and n.limit.min is not None and n.limit.max is not None
                else None
            )
        )
        for n in request.nutrients or []
    }

    # Convert daily targets to per-meal targets. The solver works per meal,
    # so ranking should too, otherwise a recipe that is reasonable for a
    # whole day looks artificially light.
    per = {k: v / request.meals_per_day for k, v in targets.items() if v is not None}

    # ------------------------------------------------------------------
    # Step 2: score a single recipe.
    #
    # score(r) = - Σ_k |value_k - target_k| / target_k
    #
    # The division by target_k normalises each nutrient so that calories
    # (order 1000) and protein (order 100) contribute comparably. When the
    # target is 0 or missing, the division falls back to 1 to avoid a
    # ZeroDivisionError; this is a defensive default, not a meaningful scale.
    # ------------------------------------------------------------------
    def score(r: Recipe) -> float:
        total = 0.0
        for k, t in per.items():
            # Nutrient keys are inconsistent across the codebase: public
            # names (calories, protein, carbs, fat) vs. internal names
            # (calories, protein_g, carbs_g, fat_g). Try both, preferring
            # the public key when present, otherwise fall back to the
            # internal alias. Unknown nutrients are silently skipped.
            value = (
                r.nutrients.get(k)
                if k in r.nutrients
                else r.nutrients.get(
                    {
                        "calories": "calories",
                        "protein": "protein_g",
                        "carbs": "carbs_g",
                        "fat": "fat_g",
                    }.get(k, k)
                )
            )
            if value is not None:
                total -= abs(value - t) / (t or 1)
        return total

    # ------------------------------------------------------------------
    # Step 3: attach scores and return the top-K pool.
    #
    # The sort key is (negative score, recipe_id) so ties break
    # deterministically by ascending ID — required for reproducible plans.
    #
    # K = min(50 * meals_per_day, 300) bounds the CP-SAT model size: with
    # horizon_days up to 14, K <= 300 keeps the model well inside the 10 s
    # solver budget. The ceiling of 300 applies regardless of meals_per_day.
    # ------------------------------------------------------------------
    for r in recipes:
        r.score = score(r)

    return sorted(recipes, key=lambda r: (-r.score, r.recipe_id))


def pool_size(request) -> int:
    """Bounded pool for the CP-SAT solver: min(50 * meals_per_day, 300)."""
    return min(50 * request.meals_per_day, 300)


def rank_candidates(recipes, request) -> list[Recipe]:
    """Top-K of the nutrient ranking, the pool the solver sees."""
    return order_candidates(recipes, request)[: pool_size(request)]
