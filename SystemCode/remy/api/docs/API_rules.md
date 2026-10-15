# API Rules & Conventions

## Standard Conventions & Errors

* **Base URL**: `[https://api.remy.app/api/v1](https://api.remy.app/api/v1)` (Prod) /
  `http://localhost:8000/api/v1` (Local)
* **Headers**:
* `Content-Type: application/json`
* `Accept: application/json` (or `text/event-stream` for SSE)


* **Standard Error Response** (FastAPI Pydantic default):

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "nutrients",
        0,
        "code"
      ],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

```

---

## Technical Standards & Error Handling

### HTTP Status Codes

| Code  | Status                | Trigger Condition                                                                   |
|-------|-----------------------|-------------------------------------------------------------------------------------|
| `200` | OK                    | Successful request execution.                                                       |
| `400` | Bad Request           | Business logic error (e.g., unresolvable recipe concept, invalid unit conversions). |
| `404` | Not Found             | Requested entity (`recipe_id`, `session_id`) does not exist.                        |
| `422` | Unprocessable Entity  | Schema or type validation failure (FastAPI Pydantic error).                         |
| `500` | Internal Server Error | Unhandled backend failure, database execution fault, or downstream service timeout. |

### Standard Error Response Envelope

All error responses return a standardized JSON envelope to simplify client-side exception handling
in JavaScript.

```json
{
  "error": {
    "code": "INVALID_NUTRIENT_RANGE",
    "message": "Nutrient limit 'min' cannot be greater than 'max'.",
    "details": [
      {
        "field": "nutrients[0].limit",
        "issue": "min (2200) > max (1800)"
      }
    ],
    "timestamp": "2026-09-16T01:00:00Z"
  }
}

```

---
