"""Slide 18 metrics, evaluated against a fully graded, identical candidate pool."""

from itertools import combinations
from math import log2


def ranking_metrics(ranked_ids: list[str], grades: dict[str, int]) -> dict[str, float | None]:
    if not ranked_ids or len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("ranking must be nonempty with unique recipe IDs")
    if set(ranked_ids) != set(grades):
        raise ValueError("grade every recipe in the recorded candidate pool, and no others")
    if any(type(grade) is not int or not 0 <= grade <= 3 for grade in grades.values()):
        raise ValueError("grades must be integers from 0 to 3")

    ordered = [grades[recipe_id] for recipe_id in ranked_ids]

    def dcg(values):
        return sum((2 ** grade - 1) / log2(position + 2)
                   for position, grade in enumerate(values[:3]))

    ideal = dcg(sorted(ordered, reverse=True))
    # ponytail: at most 300 candidates (44,850 pairs); use inversion counting for larger pools.
    pairs = [(left, right) for left, right in combinations(ordered, 2) if left != right]
    return {
        "nDCG@3": dcg(ordered) / ideal if ideal else 0.0,
        "Precision@3": sum(grade >= 2 for grade in ordered[:3]) / 3,
        "pairwise_accuracy": sum(left > right for left, right in pairs) / len(pairs) if pairs else None,
    }
