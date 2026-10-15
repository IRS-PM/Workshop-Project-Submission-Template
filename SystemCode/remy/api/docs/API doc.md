# Remy API Specification (v1)

This document outlines the REST and Streaming API endpoints for the Remy Meal Planning Service.
Built with **FastAPI** (Python) on the backend and tailored for **JavaScript/TypeScript** client
integration, all endpoints use JSON request/response payloads unless specified otherwise (e.g.,
Server-Sent Events).

---

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

## 1. POST `/api/v1/calculate/cost-and-nutrition`

Evaluates exact macronutrient/micronutrient profiles and distinguishes **consumed ingredient costs**
from **whole-package retail pricing** based on grocery data.

### Request Parameters

| Field                    | Type            | In   | Nullable / Required | Description                                      |
|--------------------------|-----------------|------|---------------------|--------------------------------------------------|
| `servings`               | `integer`       | Body | Required            | Number of target servings (min: 1).              |
| `ingredients`            | `array[object]` | Body | Required            | List of raw or canonical ingredients to analyze. |
| `ingredients[].name`     | `string`        | Body | Required            | Ingredient title or food name.                   |
| `ingredients[].quantity` | `number`        | Body | Required            | Numerical quantity (must be > 0).                |
| `ingredients[].unit`     | `string`        | Body | Required            | Unit of measure (`g`, `kg`, `ml`, `tbsp`,`pc`).  |

### Request Body Example

```json
{
  "servings": 2,
  "ingredients": [
    {
      "name": "Chicken Breast",
      "quantity": 300,
      "unit": "g"
    },
    {
      "name": "Rolled Oats",
      "quantity": 100,
      "unit": "g"
    }
  ]
}

```

### Response (`200 OK`)

```json
{
  "status": "success",
  "servings": 2,
  "summary": {
    "total_consumed_cost_sgd": null,
    "total_retail_package_cost_sgd": null,
    "nutrients": {
      "calories_kcal": 779.0,
      "protein_g": 66.08,
      "carbs_g": 67.5,
      "fat_g": 27.67,
      "fiber_g": 10.0,
      "sugar_g": 0.0,
      "sodium_mg": 429.0
    },
    "nutrients_per_serving": {
      "calories_kcal": 389.5,
      "protein_g": 33.04,
      "carbs_g": 33.75,
      "fat_g": 13.84,
      "fiber_g": 5.0,
      "sugar_g": 0.0,
      "sodium_mg": 215.0
    }
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
        "package_count": 4
      },
      "nutrients": {
        "calories_kcal": 429.0,
        "protein_g": 53.58,
        "carbs_g": 0.0,
        "fat_g": 21.42,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 429.0
      },
      "warnings": [
        {
          "code": "PARTIAL_NUTRITION_DATA",
          "message": "Some nutrient facts are missing"
        }
      ]
    },
    {
      "ingredient": "Rolled Oats",
      "canonical_name": "rolled oats",
      "fdc_id": "1136417",
      "consumed_amount_g": 100.0,
      "consumed_cost_sgd": null,
      "retail_package_cost_sgd": null,
      "matched_package": null,
      "nutrients": {
        "calories_kcal": 350.0,
        "protein_g": 12.5,
        "carbs_g": 67.5,
        "fat_g": 6.25,
        "fiber_g": 10.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0
      },
      "warnings": [
        {
          "code": "MISSING_PACKAGE_DATA",
          "message": "No usable SGD package was found"
        },
        {
          "code": "PARTIAL_NUTRITION_DATA",
          "message": "Some nutrient facts are missing"
        }
      ]
    }
  ]
}

```

---

## 2. POST `/api/v1/plan`

Generates an optimized multi-day meal plan constrained by nutrients, budget, dietary requirements,
and excluded allergens.

### Request Parameters

| Field                  | Type            | In   | Nullable / Required     | Description                                                |
|------------------------|-----------------|------|-------------------------|------------------------------------------------------------|
| `horizon_days`         | `integer`       | Body | Required                | Planning duration in days (1 to 14).                       |
| `servings`             | `integer`       | Body | Optional (Default: `1`) | Number of servings per meal slot.                          |
| `daily_budget_sgd`     | `number`        | Body | Nullable                | Max daily spending cap in SGD.                             |
| `allergies`            | `array[object]` | Body | Nullable                | Excluded allergens.                                        |
| `allergies[].code`     | `string`        | Body | Required                | Allergen identifier (e.g., `peanut`,shellfish`).           |
| `allergies[].severity` | `string`        | Body | Optional                | `mild` or `severe`.                                        |
| `dietary`              | `array[object]` | Body | Nullable                | Required dietary flags.                                    |
| `dietary[].code`       | `string`        | Body | Required                | Compliance identifier (`halal`, `vegetarian`).             |
| `nutrients`            | `array[object]` | Body | Nullable                | Targeted nutrient goals and boundaries.                    |
| `nutrients[].code`     | `string`        | Body | Required                | Nutrient key (`calories`, `protein`, `carbs`,fat`, etc.).  |
| `nutrients[].unit`     | `string`        | Body | Required                | Unit label (`kcal`, `g`, `mg`).                            |
| `nutrients[].goal`     | `object`        | Body | Nullable                | Target goal: `{"value": number}`.                          |
| `nutrients[].limit`    | `object`        | Body | Nullable                | Min/Max limits:`{"min": number, "max": number}`.           |

### Request Body Example

```json
{
  "horizon_days": 7,
  "meal_slots": [
    "breakfast",
    "lunch",
    "dinner"
  ],
  "servings": 1,
  "allergies": [
    {
      "code": "peanut",
      "severity": "severe"
    }
  ],
  "dietary": [
    {
      "code": "halal"
    }
  ],
  "nutrients": [
    {
      "code": "calories",
      "unit": "kcal",
      "goal": {
        "value": 2000
      },
      "limit": {
        "min": 1800,
        "max": 2200
      }
    },
    {
      "code": "protein",
      "unit": "g",
      "goal": {
        "value": 120
      },
      "limit": {
        "min": 100,
        "max": 140
      }
    }
  ]
}

```

### Response (`200 OK`)

```json
{
  "plan_id": "plan_99f2b8a01a",
  "status": "complete",
  "message": "Successfully generated a 7-day meal plan matching all constraints.",
  "validation_summary": {
    "carbs_status": "fulfilled",
    "allergen_status": "passed",
    "budget_status": "within_limit"
  },
  "weekly_totals": {
    "estimated_consumed_cost_sgd": 88.50,
    "avg_daily_calories_kcal": 1980
  },
  "days": [
    {
      "day": 1,
      "meals": [
        {
          "slot": "breakfast",
          "recipe_id": "rec_oatmeal_01",
          "title": "High-Protein Peanut-Free Overnight Oats",
          "estimated_cost_sgd": 2.10,
          "nutrients": {
            "calories": 450,
            "protein": 28,
            "carbs": 55
          }
        }
      ]
    }
  ]
}

```

---

## 3. POST `/api/v1/chat` (SSE Streaming)

Handles interactive conversation, recipe adjustments, and follow-up Q&A via streaming events powered
by the LangGraph engine.

### Request Parameters

| Field          | Type     | In   | Nullable / Required | Description                                                   |
|----------------|----------|------|---------------------|---------------------------------------------------------------|
| `session_id`   | `string` | Body | Required            | Chat session UUID.                                            |
| `message`      | `string` | Body | Required            | User query string.                                            |
| `user_context` | `object` | Body | Nullable            | Active context values (e.g.,`{"current_plan_id": "string"}`). |

### Request Body Example

```json
{
  "session_id": "sess_88c0a21",
  "message": "Can you swap the lunch on Day 2 with a vegetarian alternative under $5?",
  "user_context": {
    "current_plan_id": "plan_99f2b8a01a"
  }
}

```

### Server-Sent Events Protocol

The HTTP stream sends plain text `event:` and `data:` blocks. In case of an error mid-stream, an
`event: error` frame is emitted before closing the connection.

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: metadata
data: {"session_id": "sess_88c0a21", "workflow_node": "ExtractConstraints"}

event: token
data: {"delta": "I can help with "}

event: token
data: {"delta": "that! Swapping Day 2 lunch to a Tofu Warm Bowl..."}

event: plan_updated
data: {"updated_meal": {"day": 2, "slot": "lunch", "recipe_id": "rec_tofu_04", "cost_sgd": 4.20}}

event: error
data: {"code": "STREAM_INTERRUPTED", "message": "Downstream workflow timeout."}

event: done
data: {"status": "finished"}

```

---

## 4. POST `/api/v1/verify-dietary`

Verifies ingredients or recipes against explicit dietary compliance modes (halal, vegetarian) and
flags potential allergen conflicts.

### Request Parameters

| Field         | Type            | In   | Nullable / Required | Description                                                          |
|---------------|-----------------|------|---------------------|----------------------------------------------------------------------|
| `recipe_id`   | `string`        | Body | Required            | ID of the target recipe.                                             |
| `constraints` | `array[string]` | Body | Required            | Compliance rules to test (`"halal"`,`"vegetarian"`,`"peanut-free"`). |

### Request Body Example

```json
{
  "recipe_id": "rec_chicken_rice_01",
  "constraints": [
    "halal",
    "vegetarian"
  ]
}

```

### Response (`200 OK`)

```json
{
  "recipe_id": "rec_chicken_rice_01",
  "is_compliant": false,
  "status": "partial",
  "evaluations": [
    {
      "constraint": "vegetarian",
      "status": "failed",
      "reason": "Contains 'Chicken Breast' (meat product)"
    },
    {
      "constraint": "halal",
      "status": "verified",
      "reason": "Ingredients carry valid halal evidence sources"
    }
  ]
}

```

---

## 5. GET `/api/v1/recipes/{recipe_id}`

Retrieves normalized recipe data, preparation instructions, mapped FoodData Central profile
mappings, and available grocery product links.

### Request Parameters

| Field                 | Type      | In    | Nullable / Required         | Description                            |
|-----------------------|-----------|-------|-----------------------------|----------------------------------------|
| `recipe_id`           | `string`  | Path  | Required                    | Unique identifier for the recipe.      |
| `include_fulfillment` | `boolean` | Query | Optional (Default: `false`) | Include matched FairPrice retail SKUs. |

### Response (`200 OK`)

```json
{
  "recipe_id": "rec_oatmeal_01",
  "title": "High-Protein Overnight Oats",
  "instructions": [
    "Combine oats, chia seeds, and protein powder in a jar.",
    "Pour in milk and stir thoroughly.",
    "Refrigerate overnight."
  ],
  "required_food_concepts": [
    {
      "concept_name": "Rolled Oats",
      "quantity": 50,
      "unit": "g",
      "fdc_id": "173904",
      "fulfillment_offer": {
        "retailer": "FairPrice",
        "product_title": "FairPrice Whole Oats 800g",
        "price_sgd": 3.25
      }
    }
  ]
}

```

---

## 6. POST `/api/v1/recommendations/cold-start`

Serves baseline recommendations for unauthenticated or brand-new users before historical preference
context is established.

### Request Parameters

| Field                     | Type     | In   | Nullable / Required | Description                                                              |
|---------------------------|----------|------|---------------------|--------------------------------------------------------------------------|
| `dietary_preference`      | `string` | Body | Nullable            | Primary dietary preference filter (`"none"`, `"halal"`, `"vegetarian"`). |
| `target_daily_budget_sgd` | `number` | Body | Nullable            | Approximate target daily cost in SGD.                                    |

### Request Body Example

```json
{
  "dietary_preference": "none",
  "target_daily_budget_sgd": 12.00
}

```

### Response (`200 OK`)

```json
{
  "status": "success",
  "recommendations": [
    {
      "recipe_id": "rec_coldstart_01",
      "title": "Classic Egg & Avocado Toast",
      "estimated_cost_sgd": 2.50,
      "tags": [
        "quick",
        "budget-friendly"
      ]
    }
  ]
}

```

To implement client integration quickly, generate frontend API hooks or client SDKs directly using
FastAPI's auto-generated OpenAPI schema endpoint at `/openapi.json`.
