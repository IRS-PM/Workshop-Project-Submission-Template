"""Swagger response examples based on docs/calculate/calculate_api_doc.md."""

from api.core.errors import ErrorEnvelope


SUCCESS_EXAMPLE = {
    "status": "success",
    "servings": 2,
    "summary": {
        "total_consumed_cost_sgd": None,
        "total_retail_package_cost_sgd": None,
        "nutrients": {
            "calories_kcal": 779.0, "protein_g": 66.08, "carbs_g": 67.5,
            "fat_g": 27.67, "fiber_g": 10.0, "sugar_g": 0.0,
            "sodium_mg": 429.0,
        },
        "nutrients_per_serving": {
            "calories_kcal": 389.5, "protein_g": 33.04, "carbs_g": 33.75,
            "fat_g": 13.84, "fiber_g": 5.0, "sugar_g": 0.0,
            "sodium_mg": 215.0,
        },
    },
    "itemized": [
        {
            "ingredient": "Chicken Breast",
            "canonical_name": "chicken breast",
            "fdc_id": "360997",
            "consumed_amount_g": 300.0,
            "consumed_cost_sgd": 7.87,
            "retail_package_cost_sgd": 9.44,
            "matched_package": {
                "retailer": "fairprice",
                "package_title": "FarmFresh X Olagud  RTE Chicken Breast (Peri Peri)",
                "package_price_sgd": 2.36,
                "package_amount_g": 90.0,
                "package_count": 4,
            },
            "nutrients": {
                "calories_kcal": 429.0, "protein_g": 53.58, "carbs_g": 0.0,
                "fat_g": 21.42, "fiber_g": 0.0, "sugar_g": 0.0,
                "sodium_mg": 429.0,
            },
            "warnings": [{"code": "PARTIAL_NUTRITION_DATA", "message": "Some nutrient facts are missing"}],
        },
        {
            "ingredient": "Rolled Oats",
            "canonical_name": "rolled oats",
            "fdc_id": "1136417",
            "consumed_amount_g": 100.0,
            "consumed_cost_sgd": None,
            "retail_package_cost_sgd": None,
            "matched_package": None,
            "nutrients": {
                "calories_kcal": 350.0, "protein_g": 12.5, "carbs_g": 67.5,
                "fat_g": 6.25, "fiber_g": 10.0, "sugar_g": 0.0,
                "sodium_mg": 0.0,
            },
            "warnings": [
                {"code": "MISSING_PACKAGE_DATA", "message": "No usable SGD package was found"},
                {"code": "PARTIAL_NUTRITION_DATA", "message": "Some nutrient facts are missing"},
            ],
        },
    ],
}


def _error_example(code: str, message: str, details: list[dict] | None = None) -> dict:
    return {"error": {
        "code": code,
        "message": message,
        "details": details or [],
        "timestamp": "2026-09-16T17:17:22.748405+00:00",
    }}


CALCULATION_RESPONSES = {
    200: {
        "description": "Calculation succeeded. Missing data is represented by null values and per-ingredient warnings.",
        "content": {"application/json": {"example": SUCCESS_EXAMPLE}},
    },
    400: {
        "model": ErrorEnvelope,
        "description": "Ingredient resolution or unit conversion failed.",
        "content": {"application/json": {"examples": {
            "unresolvable_ingredient": {
                "summary": "Ingredient could not be matched",
                "value": _error_example("UNRESOLVABLE_INGREDIENT", "Ingredient 'Chicken Breastt' could not be resolved"),
            },
            "ambiguous_ingredient": {
                "summary": "Ingredient match is ambiguous",
                "value": _error_example("AMBIGUOUS_INGREDIENT", "Ingredient 'chicken' is ambiguous"),
            },
            "missing_unit_conversion": {
                "summary": "Tablespoon or piece conversion is unavailable",
                "value": _error_example("MISSING_UNIT_CONVERSION", "No positive grams_per_tbsp conversion is available"),
            },
        }}},
    },
    422: {
        "model": ErrorEnvelope,
        "description": "Request validation failed. details[].field identifies invalid fields using dot notation.",
        "content": {"application/json": {"example": _error_example(
            "VALIDATION_ERROR", "Request validation failed",
            [{"field": "ingredients.0.unit", "issue": "Input should be 'g', 'kg', 'ml', 'tbsp' or 'pc'"}],
        )}},
    },
    500: {
        "model": ErrorEnvelope,
        "description": "Unexpected backend or database failure.",
        "content": {"application/json": {"example": _error_example(
            "INTERNAL_ERROR", "An unexpected error occurred",
        )}},
    },
}
