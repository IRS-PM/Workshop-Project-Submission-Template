import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator


class IngredientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200, description="Ingredient name to match to food facts.", examples=["Chicken Breast"])
    quantity: PositiveFloat = Field(description="Finite quantity greater than zero.", examples=[300])
    unit: Literal["g", "kg", "ml", "tbsp", "pc"] = Field(description="Grams, kilograms, millilitres, tablespoons, or pieces.")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("quantity")
    @classmethod
    def finite_quantity(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("quantity must be finite")
        return value


class CostNutritionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "servings": 2,
        "ingredients": [
            {"name": "Chicken Breast", "quantity": 300, "unit": "g"},
            {"name": "Rolled Oats", "quantity": 100, "unit": "g"},
        ],
    }]})
    servings: int = Field(ge=1, le=1000, description="Number of target servings.")
    ingredients: list[IngredientRequest] = Field(min_length=1, max_length=100, description="Ingredients to analyze, in the desired result order.")


class Nutrients(BaseModel):
    """Nutrient amounts; individual values are null when data is unavailable."""

    calories_kcal: float | None = Field(default=None, description="Energy in kilocalories.")
    protein_g: float | None = Field(default=None, description="Protein in grams.")
    carbs_g: float | None = Field(default=None, description="Carbohydrates in grams.")
    fat_g: float | None = Field(default=None, description="Fat in grams.")
    fiber_g: float | None = Field(default=None, description="Fiber in grams.")
    sugar_g: float | None = Field(default=None, description="Sugar in grams.")
    sodium_mg: float | None = Field(default=None, description="Sodium in milligrams.")


class MatchedPackage(BaseModel):
    retailer: str | None = Field(default=None, description="Retailer identifier, such as fairprice.")
    package_title: str | None = Field(default=None, description="Matched grocery product title.")
    package_price_sgd: float | None = Field(default=None, description="Price of one package in SGD.")
    package_amount_g: float | None = Field(default=None, description="Weight of one package in grams.")
    package_count: int | None = Field(default=None, description="Whole packages needed for the requested amount.")


class ItemWarning(BaseModel):
    code: str = Field(description="Warning code: PARTIAL_NUTRITION_DATA, MISSING_PACKAGE_DATA, or ML_ASSUMED_GRAMS.")
    message: str = Field(description="Human-readable explanation of the non-fatal warning.")


class ItemizedCalculation(BaseModel):
    ingredient: str = Field(description="Ingredient name from the request, with surrounding whitespace removed.")
    canonical_name: str = Field(description="Standardized ingredient name matched in the database.")
    fdc_id: str | None = Field(description="FoodData Central identifier, if available.")
    consumed_amount_g: float | None = Field(description="Requested quantity converted to grams.")
    consumed_cost_sgd: float | None = Field(description="Cost of the consumed portion in SGD; null if pricing is unavailable.")
    retail_package_cost_sgd: float | None = Field(description="Cost of all whole packages needed in SGD; null if pricing is unavailable.")
    matched_package: MatchedPackage | None = Field(description="Selected grocery package, or null when no usable package is found.")
    nutrients: Nutrients = Field(description="Nutrition for the consumed amount of this ingredient.")
    warnings: list[ItemWarning] = Field(default_factory=list, description="Non-fatal data or conversion warnings; may be empty.")


class CalculationSummary(BaseModel):
    total_consumed_cost_sgd: float | None = Field(description="Total consumed cost in SGD; null if any ingredient lacks pricing.")
    total_retail_package_cost_sgd: float | None = Field(description="Total whole-package cost in SGD; null if any ingredient lacks pricing.")
    nutrients: Nutrients = Field(description="Total nutrition for all ingredients.")
    nutrients_per_serving: Nutrients = Field(description="Total nutrition divided by the requested servings.")


class CostNutritionResponse(BaseModel):
    status: Literal["success"] = Field(default="success", description="Always success for a completed calculation.")
    servings: int = Field(description="Number of servings echoed from the request.")
    summary: CalculationSummary = Field(description="Aggregated costs and nutrition for the whole recipe.")
    itemized: list[ItemizedCalculation] = Field(description="Per-ingredient breakdown in request order.")
