# Calculate API — Frontend Documentation

**Base URL:** `/api/v1`
**Content Type:** `application/json`

---

## 📌 Overview

This API calculates **nutrition profiles** and **cost breakdowns** for a list of ingredients. It
distinguishes between the cost of the *amount actually consumed* versus the *full retail package
price* (based on grocery data).

---

## 🔐 HTTP Status Codes

| Code  | Status                | When It Happens                                                                           | What Frontend Should Do                               |
|-------|-----------------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------|
| `200` | OK                    | Request succeeded                                                                         | Render the result normally                            |
| `400` | Bad Request           | Business logic failure (e.g., ingredient name can't be resolved, invalid unit conversion) | Show error message to user                            |
| `404` | Not Found             | Requested `recipe_id` or `session_id` doesn't exist                                       | Show "not found" state                                |
| `422` | Unprocessable Entity  | Request body failed validation (wrong types, invalid enum values)                         | Highlight invalid form fields using `details[].field` |
| `500` | Internal Server Error | Backend failure or timeout                                                                | Show generic "something went wrong" message           |

---

## 🚨 Error Response Format (All Errors)

Every error uses the **same JSON shape**, so you can write **one generic error handler**.

### Structure

| Field                   | Type                | Description                                                   |
|-------------------------|---------------------|---------------------------------------------------------------|
| `error.code`            | `string`            | Machine-readable error code (use for branching logic)         |
| `error.message`         | `string`            | Human-readable message (safe to display directly)             |
| `error.details`         | `array[object]`     | Field-level issues (useful for form validation, may be empty) |
| `error.details[].field` | `string`            | Path to the invalid field (e.g., `ingredients.0.unit`)        |
| `error.details[].issue` | `string`            | Description of what's wrong                                   |
| `error.timestamp`       | `string` (ISO 8601) | Time the error occurred                                       |

### Example

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "ingredients.0.unit",
        "issue": "Input should be 'g', 'kg', 'ml', 'tbsp' or 'pc'"
      }
    ],
    "timestamp": "2026-09-16T17:17:22.748405+00:00"
  }
}
```

---

## 1️⃣ Calculate Cost & Nutrition

```
POST /api/v1/calculate/cost-and-nutrition
```

Calculates total + per-serving nutrition, consumed cost vs. retail package cost for each ingredient.

---

### 📤 Request Body

| Field                    | Type            | Required    | Constraints                                 | Description                                |
|--------------------------|-----------------|-------------|---------------------------------------------|--------------------------------------------|
| `servings`               | `integer`       | ✅ Required | min: `1`                                    | Number of target servings                  |
| `ingredients`            | `array[object]` | ✅ Required | min items: `1`                              | List of ingredients to analyze             |
| `ingredients[].name`     | `string`        | ✅ Required | —                                           | Ingredient name (e.g., `"Chicken Breast"`) |
| `ingredients[].quantity` | `number`        | ✅ Required | must be `> 0`                               | Numeric quantity                           |
| `ingredients[].unit`     | `string`        | ✅ Required | enum: `g` \| `kg` \| `ml` \| `tbsp` \| `pc` | Unit of measure                            |

> `name` can be singular or plural, in any case: `"Tomatoes"`, `"tomato"` and `"TOMATO"` all match the
> same food. The API singularizes the name itself, so the client does not need to.

### Request Example

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

---

### 📥 Success Response — `200 OK`

#### Top-Level Fields

| Field      | Type            | Nullable | Description                                      |
|------------|-----------------|----------|--------------------------------------------------|
| `status`   | `string`        | No       | Always `"success"`                               |
| `servings` | `integer`       | No       | Echoed back from request                         |
| `summary`  | `object`        | No       | Aggregated totals for the whole recipe           |
| `itemized` | `array[object]` | No       | Per-ingredient breakdown (same order as request) |

#### `summary` Object

| Field                                   | Type     | Nullable | Description                                                           |
|-----------------------------------------|----------|----------|-----------------------------------------------------------------------|
| `summary.total_consumed_cost_sgd`       | `number` | ✅ Yes   | Total cost of *consumed amounts* (SGD). `null` if no pricing data     |
| `summary.total_retail_package_cost_sgd` | `number` | ✅ Yes   | Total cost of *full retail packages* (SGD). `null` if no pricing data |
| `summary.nutrients`                     | `object` | No       | Total nutrition for all ingredients                                   |
| `summary.nutrients_per_serving`         | `object` | No       | Total nutrition ÷ `servings`                                          |

#### Nutrient Object (`summary.nutrients`, `summary.nutrients_per_serving`, `itemized[].nutrients`)

| Field           | Type     | Nullable | Unit       |
|-----------------|----------|----------|------------|
| `calories_kcal` | `number` | ✅ Yes   | kcal       |
| `protein_g`     | `number` | ✅ Yes   | grams      |
| `carbs_g`       | `number` | ✅ Yes   | grams      |
| `fat_g`         | `number` | ✅ Yes   | grams      |
| `fiber_g`       | `number` | ✅ Yes   | grams      |
| `sugar_g`       | `number` | ✅ Yes   | grams      |
| `sodium_mg`     | `number` | ✅ Yes   | milligrams |

> ⚠️ **Note:** Individual nutrient values can be `null` when data is unavailable. Always null-check
> before arithmetic.

#### `itemized[]` Object

| Field                               | Type               | Nullable | Description                                               |
|-------------------------------------|--------------------|----------|-----------------------------------------------------------|
| `ingredient`                        | `string`           | No       | Original name from request                                |
| `canonical_name`                    | `string`           | No       | Standardized/matched name                                 |
| `fdc_id`                            | `string`           | ✅ Yes   | FoodData Central database ID                              |
| `consumed_amount_g`                 | `number`           | ✅ Yes   | Converted amount in grams                                 |
| `consumed_cost_sgd`                 | `number`           | ✅ Yes   | Cost of the consumed portion (SGD)                        |
| `retail_package_cost_sgd`           | `number`           | ✅ Yes   | Cost of the full retail package(s) needed (SGD)           |
| `matched_package`                   | `object` \| `null` | ✅ Yes   | Grocery package match — `null` if none found              |
| `matched_package.retailer`          | `string`           | No       | Retailer identifier (e.g., `"fairprice"`)                 |
| `matched_package.package_title`     | `string`           | No       | Product title                                             |
| `matched_package.package_price_sgd` | `number`           | No       | Price per package (SGD)                                   |
| `matched_package.package_amount_g`  | `number`           | No       | Weight per package (grams)                                |
| `matched_package.package_count`     | `integer`          | No       | Number of packages needed                                 |
| `nutrients`                         | `object`           | No       | Nutrition for this ingredient (see Nutrient Object above) |
| `warnings`                          | `array[object]`    | No       | Non-fatal warnings (may be empty)                         |

#### `itemized[].warnings[]` Object

| Field     | Type     | Description                    |
|-----------|----------|--------------------------------|
| `code`    | `string` | Warning code (see table below) |
| `message` | `string` | Human-readable warning text    |

#### Known Warning Codes

| Code                     | Meaning                           | Suggested UI Behavior                      |
|--------------------------|-----------------------------------|--------------------------------------------|
| `PARTIAL_NUTRITION_DATA` | Some nutrient facts are missing   | Show a small info badge                    |
| `MISSING_PACKAGE_DATA`   | No SGD package/pricing data found | Hide or gray out cost fields for that item |

---

### Success Response Example

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

## ❌ Error Responses

### `400 Bad Request` — Unresolvable Ingredient

Occurs when an ingredient name can't be matched to the food database.

```json
{
  "error": {
    "code": "UNRESOLVABLE_INGREDIENT",
    "message": "Ingredient 'Chicken Breastt' could not be resolved",
    "details": [],
    "timestamp": "2026-09-16T17:12:47.151238+00:00"
  }
}
```

**Frontend tip:** `details` is empty here — parse the offending ingredient name out of `message` if
you need to highlight the field.

### `422 Unprocessable Entity` — Validation Error

Occurs when the request body violates schema rules (wrong type, invalid enum, etc.).

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "ingredients.0.unit",
        "issue": "Input should be 'g', 'kg', 'ml', 'tbsp' or 'pc'"
      }
    ],
    "timestamp": "2026-09-16T17:17:22.748405+00:00"
  }
}
```

**Frontend tip:** `details[].field` uses **dot notation with array indices** (`ingredients.0.unit` =
first ingredient's unit). Map these directly to your form input refs.

---

## 🧑‍💻 Frontend Integration Cheat Sheet

```js
async function calculateCostAndNutrition(payload) {
    const res = await fetch('/api/v1/calculate/cost-and-nutrition', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
        // Uniform error envelope for ALL error statuses
        throw new ApiError(res.status, data.error.code, data.error.message, data.error.details);
    }

    return data; // { status, servings, summary, itemized }
}
```

**Key reminders:**

1. ✅ **Null-check** all cost and nutrient fields before display or math.
2. ⚠️ **Render warnings** per itemized ingredient — a `200` response can still contain incomplete
   data.
3. 📏 **Validate `unit` client-side** against the enum (`g`, `kg`, `ml`, `tbsp`, `pc`) to avoid `422`
   round-trips.
4. 🔢 **`quantity` must be > 0** — enforce with form validation before submitting.
