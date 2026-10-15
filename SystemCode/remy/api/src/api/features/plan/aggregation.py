def aggregate(days, request):
    keys = sorted({k for day in days for r in day for k in r.nutrients})
    totals = {k: sum((r.nutrients.get(k) or 0) * request.servings for day in days for r in day) for
              k in keys}
    horizon = {f"avg_daily_{k}": round(v / request.horizon_days, 2) for k, v in totals.items()}
    return horizon
