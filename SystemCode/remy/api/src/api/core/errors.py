from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str | None = Field(default=None, description="Invalid field path using dot notation, such as ingredients.0.unit.")
    issue: str = Field(description="Description of the field-level problem.")


class ErrorBody(BaseModel):
    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    details: list[ErrorDetail] = Field(default_factory=list, description="Field-level issues; may be empty.")
    timestamp: datetime = Field(description="Time the error occurred, in ISO 8601 format.")


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def error_envelope(code: str, message: str, details: list[ErrorDetail] | None = None) -> dict:
    return {"error": {"code": code, "message": message,
                       "details": [d.model_dump() for d in (details or [])],
                       "timestamp": datetime.now(timezone.utc).isoformat()}}
