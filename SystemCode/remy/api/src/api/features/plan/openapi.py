from api.core.errors import ErrorEnvelope

STREAM_EXAMPLE = (
    'event: progress\n'
    'data: {"stage":"loading","message":"Loading recipes","step":1,"total":3}\n\n'
    'event: progress\n'
    'data: {"stage":"selecting","message":"Choosing recipes that fit","step":2,"total":3}\n\n'
    'event: progress\n'
    'data: {"stage":"solving","message":"Balancing your days","step":3,"total":3}\n\n'
    ': keep-alive\n\n'
    'event: text\n'
    'data: {"text":"Day 1: Chickpea & Spinach Curry (640 kcal). About 640 kcal in all.\\n"}\n\n'
    'event: plan\n'
    'data: {"plan_id":"plan_a1b2c3d4e5","status":"complete",'
    '"message":"Successfully generated a 1-day meal plan.",'
    '"validation_summary":{"allergen_status":"not_requested","dietary_status":"not_requested"},'
    '"relaxations":[],"horizon_totals":{"avg_daily_calories":640.0,"avg_daily_protein_g":28.5},'
    '"days":[{"day":1,"meals":[{"slot":"meal_1","recipe_id":"r_1042",'
    '"title":"Chickpea & Spinach Curry","nutrients":{"calories":640.0,"protein_g":28.5},'
    '"ingredients":[{"quantity":200.0,"unit":"g","text":"canned chickpeas",'
    '"preparation":"drained","optional":false}],'
    '"instructions":"Simmer for 15 minutes."}]}]}\n\n'
)

ERROR_EVENT_EXAMPLE = (
    'event: progress\n'
    'data: {"stage":"loading","message":"Loading recipes","step":1,"total":3}\n\n'
    'event: error\n'
    'data: {"error":{"code":"PLAN_INFEASIBLE","message":"No feasible plan after all relaxations",'
    '"details":[],"timestamp":"2026-10-03T03:14:16.697+00:00"}}\n\n'
)

PLAN_DESCRIPTION = (
    "Generates a `horizon_days` x `meals_per_day` meal plan and streams it as "
    "Server-Sent Events (`text/event-stream`).\n\n"
    "Events, in order:\n"
    "- `progress`: `{stage, message, step, total}` as each step starts "
    "(`loading`, `selecting`, `solving`).\n"
    "- `: keep-alive` comment lines every 10 seconds while a step is still running.\n"
    "- `text`: `{text}`, a plain-text overview of the plan, one line per day. The server "
    "buffers it and flushes every 100 words (the last chunk may be shorter); join the chunks "
    "in order to get the full text.\n"
    "- `plan`: the finished plan, in the same shape the endpoint used to return as JSON. "
    "The stream ends after it.\n"
    "- `error`: the shared error envelope, for failures after the stream has started "
    "(`NO_CANDIDATES`, `UNSUPPORTED_UNIT`, `PLAN_INFEASIBLE`, `INTERNAL_ERROR`). "
    "The stream ends after it.\n\n"
    "Unknown allergen, dietary or nutrient codes, an invalid nutrient range, and body "
    "validation errors are rejected before the stream starts, with a normal JSON "
    "`400` or `422` response."
)

PLAN_RESPONSES = {
    200: {
        "description": "Server-Sent Events stream ending in a `plan` or `error` event.",
        "content": {
            "text/event-stream": {
                "schema": {"type": "string"},
                "examples": {
                    "plan": {"summary": "Successful plan", "value": STREAM_EXAMPLE},
                    "error": {"summary": "Failure after the stream started", "value": ERROR_EVENT_EXAMPLE},
                },
            }
        },
    },
    400: {
        "model": ErrorEnvelope,
        "description": "Unknown allergen, dietary or nutrient code, or a nutrient minimum above its maximum.",
    },
    422: {"model": ErrorEnvelope, "description": "Request body failed validation."},
}
