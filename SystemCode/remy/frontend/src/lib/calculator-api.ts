export type IngredientUnit = "g" | "kg" | "ml" | "tbsp" | "pc";

export type CalculationRequest = {
  servings: number;
  ingredients: { name: string; quantity: number; unit: IngredientUnit }[];
};

export type Nutrients = {
  calories_kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  sugar_g: number | null;
  sodium_mg: number | null;
};

export type CalculationResponse = {
  status: "success";
  servings: number;
  summary: {
    total_consumed_cost_sgd: number | null;
    total_retail_package_cost_sgd: number | null;
    nutrients: Nutrients;
    nutrients_per_serving: Nutrients;
  };
  itemized: {
    ingredient: string;
    canonical_name: string;
    consumed_amount_g: number | null;
    matched_package: {
      retailer: string | null;
      package_title: string | null;
      package_count: number | null;
    } | null;
    warnings: { code: string; message: string }[];
  }[];
};

export async function calculateIngredient(
  request: CalculationRequest,
): Promise<CalculationResponse> {
  if (!Number.isInteger(request.servings) || request.servings < 1 || request.servings > 1000) {
    throw new Error("Enter a whole number of servings between 1 and 1,000.");
  }
  if (!request.ingredients.length || request.ingredients.some((item) =>
    !item.name.trim() || item.name.length > 200 || !Number.isFinite(item.quantity) || item.quantity <= 0,
  )) {
    throw new Error("Enter an ingredient name and a quantity greater than zero.");
  }

  let response: Response;
  try {
    // Next.js proxies /api/v1/* to the Remy API (REMY_API_URL in next.config.ts).
    response = await fetch("/api/v1/calculate/cost-and-nutrition", {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(20_000),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new Error("The calculation took too long. Please try again.");
    }
    throw new Error("Cannot reach the calculation service. Please try again.");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.error?.message;
    const details: unknown = payload?.error?.details;
    const issues = Array.isArray(details)
      ? details.flatMap((detail) => typeof detail?.issue === "string" ? [detail.issue] : [])
      : [];
    throw new Error([
      typeof message === "string" ? message : "The calculation service is unavailable. Please try again.",
      ...issues,
    ].join(" "));
  }
  if (payload?.status !== "success" || !payload.summary?.nutrients ||
      !payload.summary?.nutrients_per_serving || !Array.isArray(payload.itemized)) {
    throw new Error("The calculation service returned an unexpected response. Please try again.");
  }
  return payload as CalculationResponse;
}
