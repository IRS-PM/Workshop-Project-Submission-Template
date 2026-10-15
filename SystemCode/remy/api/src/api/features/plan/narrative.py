from collections.abc import Iterator

from .schemas import MealResponse, PlanResponse


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _meal(meal: MealResponse) -> str:
    calories = meal.nutrients.get("calories")
    return meal.title if calories is None else f"{meal.title} ({calories:,.0f} kcal)"


def plan_text(plan: PlanResponse) -> Iterator[str]:
    """Describe the plan one day at a time, as plain text."""
    for day in plan.days:
        if not day.meals:
            continue
        line = f"Day {day.day}: {_join([_meal(meal) for meal in day.meals])}."
        calories = sum(meal.nutrients.get("calories", 0) for meal in day.meals)
        if calories:
            line += f" About {calories:,.0f} kcal in all."
        yield line + "\n"
