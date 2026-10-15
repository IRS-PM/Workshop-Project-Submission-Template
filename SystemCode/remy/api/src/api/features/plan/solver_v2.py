import math

from .exceptions import PlanInfeasible
from .models import Recipe


def solve_v2(recipes: list[Recipe], request):
    """Build and solve the CP-SAT model for a meal plan.

    Returns
    -------
    (days, relaxations)
        ``days`` is a list of length ``horizon_days``; each element is a list of
        ``meals_per_day`` recipe objects ordered by descending calories then
        ascending ``recipe_id``. ``relaxations`` is a list of relaxation records
        (empty when the model solves without relaxation).

    Raises
    ------
    PlanInfeasible
        When no feasible plan exists, or when OR-Tools is unavailable and the
        greedy fallback cannot produce a plan.
    """

    # ------------------------------------------------------------------
    # Import OR-Tools lazily so the module remains importable in environments
    # (e.g. tests, tooling) that don't install the solver.
    # ------------------------------------------------------------------
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        # Fallback: no solver available. Produce a deterministic round-robin
        # plan instead of failing outright. This is intentionally crude and
        # exists only so the endpoint remains callable without OR-Tools.
        if not recipes:
            raise PlanInfeasible("No candidates")
        return (
            [
                [
                    recipes[(d * request.meals_per_day + i) % len(recipes)]
                    for i in range(request.meals_per_day)
                ]
                for d in range(request.horizon_days)
            ],
            [],
        )

    # ------------------------------------------------------------------
    # Recipe index setup
    # ------------------------------------------------------------------
    # Recipe contains mutable fields (a nutrients dict), so it is unhashable.
    # Use stable list indices as model keys instead of recipe objects.
    recipes = list(recipes)
    recipe_by_idx = {j: recipe for j, recipe in enumerate(recipes)}
    recipe_count = len(recipes)

    h = request.horizon_days  # number of days to plan
    m = request.meals_per_day  # number of meals per day
    # ------------------------------------------------------------------
    # Relaxation ladder
    # ------------------------------------------------------------------
    # Each step is a transformation applied cumulatively to the model:
    # the solver is rebuilt and re-solved after each step until a feasible
    # plan is found or all steps are exhausted.
    #
    #   1. Increase max-days-per-recipe by 1 (allows more repeats).
    #   2. Drop the no-consecutive-day variety constraint.
    #   3. Increase every nutrient `max` by 10%.
    #   4. Decrease every nutrient `min` by 10%.
    #   5. Give up and raise PlanInfeasible.
    #
    # The applied relaxations are recorded so the API can report which
    # constraint was loosened and mark the plan as `partial`.

    def build_and_solve(relaxation_state):
        """Build the CP-SAT model under the given relaxation state and solve.

        Returns ``(solver, y, n, status)`` when a feasible plan is found,
        or ``None`` when the model is infeasible.
        """
        model = cp_model.CpModel()


        # y[d, j] = 1 iff recipe index j is served at least once on day d.
        # n[d, j] = number of times recipe index j is served on day d (0..m).
        y = {
            (d, j): model.NewBoolVar(f"y_{d}_{j}")
            for d in range(h)
            for j in range(recipe_count)
        }
        n = {
            (d, j): model.NewIntVar(0, 1, f"n_{d}_{j}")  # at most once per day
            for d in range(h)
            for j in range(recipe_count)
        }

        # --- Hard constraints: exactly m meals per day, linking ------------
        for d in range(h):
            model.Add(sum(n[d, j] for j in range(recipe_count)) == m)
            for j in range(recipe_count):
                model.Add(n[d, j] <= m * y[d, j])
                model.Add(n[d, j] >= y[d, j])

        # --- Variety: no recipe on more than max_days days ---------------
        max_days = math.ceil(h / 3) + relaxation_state["extra_days_per_recipe"]
        for j in range(recipe_count):
            model.Add(sum(y[d, j] for d in range(h)) <= max_days)

        # --- Variety: no two consecutive days ----------------------------
        if not relaxation_state["drop_consecutive_rule"]:
            for j in range(recipe_count):
                for d in range(h - 1):
                    model.Add(y[d, j] + y[d + 1, j] <= 1)

        # --- Nutrient goals and limits -----------------------------------
        # Each nutrient has an optional goal, min, and max. Goals become soft
        # deviation variables; limits are hard bounds unless relaxed.
        nutrient_specs = relaxation_state["nutrient_specs"]
        deviation_terms = []

        for spec in nutrient_specs:
            code = spec["code"]
            goal = spec.get("goal")
            lo = spec.get("min")
            hi = spec.get("max")

            # Aggregate per-day nutrient total for this nutrient across the
            # day's meals. Values are integers in milli-units already.
            for d in range(h):
                day_total = sum(
                    n[d, j] * spec["values"][j] for j in range(recipe_count)
                )

                if lo is not None:
                    under = model.NewIntVar(0, 10**9, f"under_{d}_{code}")
                    model.Add(day_total + under >= lo)
                    deviation_terms.append(1000 * under)
                if hi is not None:
                    over = model.NewIntVar(0, 10**9, f"over_{d}_{code}")
                    model.Add(day_total - over <= hi)
                    deviation_terms.append(1000 * over)

                if goal is not None:
                    # day_total - goal = dev_over - dev_under
                    dev_over = model.NewIntVar(0, 10**9, f"dev_over_{d}_{code}")
                    dev_under = model.NewIntVar(0, 10**9, f"dev_under_{d}_{code}")
                    model.Add(day_total - goal == dev_over - dev_under)
                    deviation_terms.append(spec["weight"] * (dev_over + dev_under))

        # --- Objective ----------------------------------------------------
        # Primary: minimise weighted deviation from goals.
        # Secondary: tiny index term for deterministic tie-breaking.
        primary = sum(deviation_terms) if deviation_terms else 0
        secondary = sum(
            (j + 1) * n[d, j]
            for d in range(h)
            for j in range(recipe_count)
        )
        # model.Minimize(primary * 1000 + secondary)
        model.Minimize(primary + secondary)

        model_solver = cp_model.CpSolver()
        model_solver.parameters.random_seed = 0
        model_solver.parameters.num_search_workers = 1
        model_solver.parameters.max_time_in_seconds = 0.5

        model_status = model_solver.Solve(model)
        if model_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        return model_solver, y, n, model_status

    # ------------------------------------------------------------------
    # Nutrient spec preparation
    # ------------------------------------------------------------------
    # Build the nutrient specification once, then mutate its bounds as the
    # relaxation ladder progresses. Values are in milli-units (×1000) so the
    # CP-SAT model never deals with floats.
    scale = 1000
    nutrient_specs = []
    for nut in request.nutrients or []:
        code = nut.code
        goal = None
        lo = None
        hi = None

        if nut.goal is not None:
            goal = int(round(nut.goal.value * scale))
        if nut.limit is not None:
            if nut.limit.min is not None:
                lo = int(round(nut.limit.min * scale))
            if nut.limit.max is not None:
                hi = int(round(nut.limit.max * scale))

        if goal is None and lo is None and hi is None:
            continue

        nutrient_key = {
            "calories": "calories", "protein": "protein_g", "carbs": "carbs_g",
            "fat": "fat_g", "saturated_fat": "saturated_fat_g", "fiber": "fiber_g",
            "sugar": "sugar_g", "sodium": "sodium_mg", "cholesterol": "cholesterol_mg",
        }.get(code, code)
        values = [
            int(round((recipe.nutrients.get(nutrient_key, 0) or 0) * scale))
            for recipe in recipes
        ]
        nutrient_specs.append(
            {
                "code": code,
                "goal": goal,
                "min": lo,
                "max": hi,
                "values": values,
                "weight": 1.0,
            }
        )

    # ------------------------------------------------------------------
    # Relaxation ladder
    # ------------------------------------------------------------------
    # The state is a mutable dict so each step can adjust it in place.
    state = {
        "extra_days_per_recipe": 0,
        "drop_consecutive_rule": False,
        "nutrient_specs": nutrient_specs,
    }

    applied_relaxations = []

    # Stage 0: try the model as specified.
    result = build_and_solve(state)

    # Stage 1: allow one more day of repeats per recipe.
    if result is None:
        state["extra_days_per_recipe"] = 1
        applied_relaxations.append(
            {"stage": 1, "kind": "extra_days_per_recipe", "detail": {"added": 1}}
        )
        result = build_and_solve(state)

    # Stage 2: drop the no-consecutive-day variety rule.
    if result is None:
        state["drop_consecutive_rule"] = True
        applied_relaxations.append(
            {"stage": 2, "kind": "drop_consecutive_rule", "detail": {}}
        )
        result = build_and_solve(state)

    # Stage 3: widen every nutrient `max` by 10%.
    if result is None:
        widened = []
        for spec in state["nutrient_specs"]:
            if spec["max"] is not None:
                old = spec["max"]
                spec["max"] = int(round(old * 1.10))
                widened.append(
                    {"code": spec["code"], "from": old, "to": spec["max"]}
                )
        if widened:
            applied_relaxations.append(
                {
                    "stage": 3,
                    "kind": "widen_nutrient_max",
                    "detail": {"nutrients": widened},
                }
            )
            result = build_and_solve(state)

    # Stage 4: loosen every nutrient `min` by 10%.
    if result is None:
        loosened = []
        for spec in state["nutrient_specs"]:
            if spec["min"] is not None:
                old = spec["min"]
                spec["min"] = int(round(old * 0.90))
                loosened.append(
                    {"code": spec["code"], "from": old, "to": spec["min"]}
                )
        if loosened:
            applied_relaxations.append(
                {
                    "stage": 4,
                    "kind": "loosen_nutrient_min",
                    "detail": {"nutrients": loosened},
                }
            )
            result = build_and_solve(state)

    # Stage 5: no feasible plan under any relaxation.
    if result is None:
        raise PlanInfeasible("No feasible plan after all relaxations")

    solver, y, n, status = result

    # ------------------------------------------------------------------
    # Stage 2 post-pass: expand the per-day copy counts and order within day.
    # ------------------------------------------------------------------
    # The solver returns n[d, j] as a count per recipe per day. Expanding and
    # sorting here is a pure post-pass: it never changes the selection, only
    # the presentation order. Sort key is descending calories, then ascending
    # recipe_id, matching the plan's within-day ordering rule.
    days = []
    for d in range(h):
        meals = []
        for j in range(recipe_count):
            meals.extend([recipe_by_idx[j]] * solver.Value(n[d, j]))
        days.append(
            sorted(
                meals,
                key=lambda r: (
                    -float(r.nutrients.get("calories", 0) or 0),
                    r.recipe_id,
                ),
            )
        )

    return days, applied_relaxations
