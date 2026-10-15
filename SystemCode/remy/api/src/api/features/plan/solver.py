"""Backward-compatible import for the authoritative plan solver."""
from .solver_v2 import solve_v2


def solve(recipes, request):
    return solve_v2(recipes, request)
