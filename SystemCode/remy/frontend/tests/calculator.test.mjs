import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import { normalizeIngredientName } from "../src/lib/ingredient-normalization.ts";
import { calculateIngredient } from "../src/lib/calculator-api.ts";

afterEach(() => mock.restoreAll());

test("ingredient cleanup handles case, skip words, punctuation, and irregular plurals", () => {
  for (const [input, expected] of [
    ["  Fresh chopped TOMATOES! ", "tomato"],
    ["The chicken breasts", "chicken breast"],
    ["Rolled Oats", "rolled oat"],
    ["finely sliced blueberries", "blueberry"],
    ["leaves", "leaf"],
    ["Crème brûlée", "creme brulee"],
  ]) {
    assert.equal(normalizeIngredientName(input), expected);
    assert.equal(normalizeIngredientName(expected), expected);
  }
});

test("normalization preserves meaningful food descriptors and singular food names", () => {
  for (const name of ["asparagus", "couscous", "hummus", "molasses", "watercress", "fish", "rice", "raw chicken", "unsalted butter"]) {
    assert.equal(normalizeIngredientName(name), name);
  }
  assert.equal(normalizeIngredientName("white beans"), "white bean");
  assert.equal(normalizeIngredientName("red onions"), "red onion");
  assert.equal(normalizeIngredientName("gluten-free noodles"), "gluten free noodle");
});

test("empty and skipword-only input has no ingredient", () => {
  for (const value of ["", "   ", "!!!", "the fresh finely chopped"]) {
    assert.equal(normalizeIngredientName(value), "");
  }
});

const request = {
  servings: 2,
  ingredients: [{ name: normalizeIngredientName("Fresh Chicken Breasts"), quantity: 300, unit: "g" }],
};

test("calculator submits normalized names and amounts through the calculation proxy", async () => {
  const nutrients = Object.fromEntries(["calories_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"].map((key) => [key, null]));
  const result = { status: "success", servings: 2, summary: { total_consumed_cost_sgd: null, total_retail_package_cost_sgd: null, nutrients, nutrients_per_serving: nutrients }, itemized: [] };
  const fetchMock = mock.method(globalThis, "fetch", async () => Response.json(result));
  assert.deepEqual(await calculateIngredient(request), result);
  const [url, options] = fetchMock.mock.calls[0].arguments;
  assert.equal(url, "/api/v1/calculate/cost-and-nutrition");
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "omit");
  assert.deepEqual(JSON.parse(options.body), {
    servings: 2,
    ingredients: [{ name: "chicken breast", quantity: 300, unit: "g" }],
  });
});

test("invalid amounts, servings, and names are rejected before a request", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => { throw new Error("must not call"); });
  for (const servings of [0, 1.5, 1001, NaN]) {
    await assert.rejects(calculateIngredient({ ...request, servings }), /whole number/);
  }
  for (const quantity of [0, -1, NaN, Infinity]) {
    await assert.rejects(calculateIngredient({ ...request, ingredients: [{ ...request.ingredients[0], quantity }] }), /greater than zero/);
  }
  await assert.rejects(calculateIngredient({ ...request, ingredients: [{ ...request.ingredients[0], name: "" }] }), /ingredient name/);
  assert.equal(fetchMock.mock.callCount(), 0);
});

test("API errors expose the shared envelope and field issues", async () => {
  mock.method(globalThis, "fetch", async () => Response.json({ error: {
    message: "Request validation failed",
    details: [{ field: "ingredients.0.unit", issue: "Unsupported unit" }],
  } }, { status: 422 }));
  await assert.rejects(calculateIngredient(request), /Request validation failed Unsupported unit/);
});

test("offline, timeout, and non-JSON responses provide useful messages", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(calculateIngredient(request), /Cannot reach/);
  fetchMock.mock.mockImplementation(async () => { throw new DOMException("Timeout", "TimeoutError"); });
  await assert.rejects(calculateIngredient(request), /too long/);
  fetchMock.mock.mockImplementation(async () => new Response("Bad gateway", { status: 502 }));
  await assert.rejects(calculateIngredient(request), /service is unavailable/);
  fetchMock.mock.mockImplementation(async () => Response.json({}));
  await assert.rejects(calculateIngredient(request), /unexpected response/);
});
