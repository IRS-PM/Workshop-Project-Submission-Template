import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _code(value: str) -> str:
    value = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not value:
        raise ValueError("code must not be blank")
    return value


class AllergyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=64)
    severity: Literal["mild", "severe"] | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v): return _code(v)


class DietaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=64)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v): return _code(v)


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float

    @field_validator("value")
    @classmethod
    def finite(cls, v):
        if not math.isfinite(v): raise ValueError("value must be finite")
        return v


class NutrientLimit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: float | None = None
    max: float | None = None

    @field_validator("min", "max")
    @classmethod
    def finite(cls, v):
        if v is not None and not math.isfinite(v): raise ValueError("limit must be finite")
        return v


class NutrientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=16)
    goal: Goal | None = None
    limit: NutrientLimit | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v): return _code(v)

    @model_validator(mode="after")
    def has_target(self):
        if self.goal is None and self.limit is None: raise ValueError("goal or limit is required")
        return self


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    horizon_days: int = Field(ge=1, le=14)
    meals_per_day: int = Field(ge=1, le=6)
    servings: int = Field(default=1, ge=1)
    allergies: list[AllergyRequest] | None = None
    dietary: list[DietaryRequest] | None = None
    nutrients: list[NutrientRequest] | None = None
    # Optional. A run keeps its checkpoints under this id: sending the same id again
    # resumes an unfinished run, or returns the stored plan of a finished one.
    run_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")

    @model_validator(mode="after")
    def unique_codes(self):
        for name, values in (("allergies", self.allergies), ("dietary", self.dietary),
                             ("nutrients", self.nutrients)):
            codes = [x.code for x in values or []]
            if len(codes) != len(set(codes)): raise ValueError(f"duplicate {name} code")
        for n in self.nutrients or []:
            if n.limit and n.limit.min is not None and n.limit.max is not None and n.limit.min > n.limit.max:
                raise ValueError("min cannot be greater than max")
        return self


class MealIngredientResponse(BaseModel):
    quantity: float | None
    unit: str | None
    text: str | None
    preparation: str | None
    optional: bool


class MealResponse(BaseModel):
    slot: str
    recipe_id: str
    title: str
    nutrients: dict[str, float]
    ingredients: list[MealIngredientResponse]
    instructions: str | None


class DayResponse(BaseModel):
    day: int
    meals: list[MealResponse]


class RelaxationRecord(BaseModel):
    stage: int
    kind: str
    detail: dict = Field(default_factory=dict)


class PlanResponse(BaseModel):
    plan_id: str
    trace_id: str | None = None
    evaluation_id: str | None = None
    status: Literal["complete", "partial"]
    message: str
    validation_summary: dict
    relaxations: list[RelaxationRecord] = Field(default_factory=list)
    horizon_totals: dict[str, float]
    days: list[DayResponse]
