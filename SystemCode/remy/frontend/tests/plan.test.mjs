import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import {
  createSseParser,
  describeRelaxation,
  formatIngredient,
  formatNutrient,
  generatePlan,
  nutrientInfo,
  sortedNutrients,
} from "../src/lib/plan-api.ts";

afterEach(() => mock.restoreAll());

const request = {
  horizon_days: 3,
  meals_per_day: 3,
  servings: 2,
  allergies: [{ code: "peanut" }],
  dietary: [{ code: "vegetarian" }],
  nutrients: [
    { code: "calories", unit: "kcal", goal: { value: 2000 } },
    { code: "protein", unit: "g", limit: { min: 60, max: 120 } },
  ],
};

const plan = {
  plan_id: "plan_a1b2c3d4e5",
  status: "complete",
  message: "Successfully generated a 3-day meal plan.",
  validation_summary: { allergen_status: "passed", dietary_status: "passed" },
  relaxations: [],
  horizon_totals: { avg_daily_calories: 1985.4 },
  days: [],
};

const encoder = new TextEncoder();
const event = (name, data) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
const progress = (step, stage, message) => event("progress", { stage, message, step, total: 3 });

function stream(chunks, init = {}) {
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }), { headers: { "content-type": "text/event-stream; charset=utf-8" }, ...init });
}

function splitEvery(text, size) {
  const parts = [];
  for (let i = 0; i < text.length; i += size) parts.push(text.slice(i, i + size));
  return parts;
}

const fullStream = progress(1, "loading", "Loading recipes") +
  ": keep-alive\n\n" +
  progress(2, "selecting", "Choosing recipes that fit") +
  progress(3, "solving", "Balancing your days") +
  event("plan", plan);

test("plan requests stream through the /api/v1 proxy and report progress", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => stream(splitEvery(fullStream, 7)));
  const seen = [];
  assert.deepEqual(await generatePlan(request, { onProgress: (p) => seen.push(`${p.step}/${p.total} ${p.stage}`) }), plan);
  assert.deepEqual(seen, ["1/3 loading", "2/3 selecting", "3/3 solving"]);
  const [url, options] = fetchMock.mock.calls[0].arguments;
  assert.equal(url, "/api/v1/plan");
  assert.equal(options.method, "POST");
  assert.equal(options.credentials, "omit");
  assert.equal(options.headers.Accept, "text/event-stream");
  assert.deepEqual(JSON.parse(options.body), request);
});

test("text chunks reach onText in order, before the plan resolves", async () => {
  const first = "Day 1: Chickpea Curry (640 kcal). About 640 kcal in all.\nDay 2:";
  const second = " Oat Bowl (420 kcal). About 420 kcal in all.\n";
  mock.method(globalThis, "fetch", async () => stream(splitEvery(
    progress(3, "solving", "Balancing your days") +
      event("text", { text: first }) +
      event("text", { text: second }) +
      event("text", { nope: true }) +
      event("plan", plan),
    5,
  )));
  const chunks = [];
  const result = await generatePlan(request, { onText: (chunk) => chunks.push(chunk) });
  assert.deepEqual(result, plan);
  assert.deepEqual(chunks, [first, second]);
  assert.equal(chunks.join(""), `${first}${second}`);
});

test("empty limit bounds are dropped from the payload", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => stream([event("plan", plan)]));
  await generatePlan({
    horizon_days: 7,
    meals_per_day: 3,
    servings: 1,
    nutrients: [{ code: "sodium", unit: "mg", limit: { min: undefined, max: 2300 } }],
  });
  assert.deepEqual(JSON.parse(fetchMock.mock.calls[0].arguments[1].body).nutrients, [
    { code: "sodium", unit: "mg", limit: { max: 2300 } },
  ]);
});

test("the SSE parser handles split chunks, CRLF, comments, and multi-line data", () => {
  const events = [];
  const feed = createSseParser((e) => events.push(e));
  for (const part of ["event: progr", "ess\r\ndata: {\"step\":1}\r\n", "\r\n: keep-alive\n\n", "data: line one\ndata: line two\n\n"]) {
    feed(part);
  }
  assert.deepEqual(events, [
    { event: "progress", data: '{"step":1}' },
    { event: "message", data: "line one\nline two" },
  ]);
});

test("out-of-range plans and incomplete nutrient targets are rejected before a request", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => { throw new Error("must not call"); });
  for (const horizon_days of [0, 15, 2.5, NaN]) {
    await assert.rejects(generatePlan({ ...request, horizon_days }), /1 and 14 days/);
  }
  for (const meals_per_day of [0, 7, 1.5]) {
    await assert.rejects(generatePlan({ ...request, meals_per_day }), /1 and 6 meals/);
  }
  for (const servings of [0, -1, 1.5]) {
    await assert.rejects(generatePlan({ ...request, servings }), /servings/);
  }
  await assert.rejects(
    generatePlan({ ...request, nutrients: [{ code: "fiber", unit: "g" }] }),
    /Give Fibre a target/,
  );
  await assert.rejects(
    generatePlan({ ...request, nutrients: [{ code: "fat", unit: "g", limit: { min: 90, max: 40 } }] }),
    /Fat minimum cannot be greater/,
  );
  await assert.rejects(
    generatePlan({ ...request, nutrients: [request.nutrients[0], request.nutrients[0]] }),
    /Calories is listed more than once/,
  );
  await assert.rejects(
    generatePlan({ ...request, nutrients: [{ code: "sugar", unit: "g", goal: { value: Infinity } }] }),
    /numbers of 0 or more/,
  );
  assert.equal(fetchMock.mock.callCount(), 0);
});

test("errors before the stream use the JSON envelope", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => Response.json({ error: {
    code: "VALIDATION_ERROR",
    message: "Request validation failed",
    details: [{ field: "meals_per_day", issue: "Input should be less than or equal to 6" }],
  } }, { status: 422 }));
  await assert.rejects(generatePlan(request), /Request validation failed Input should be less than or equal to 6/);

  fetchMock.mock.mockImplementation(async () => Response.json({ error: {
    code: "UNKNOWN_ALLERGEN", message: "Unknown allergen: tree_nut", details: [],
  } }, { status: 400 }));
  await assert.rejects(generatePlan(request), /Unknown allergen: tree_nut/);
});

test("error events inside the stream use friendly copy for planner failures", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => stream([
    progress(1, "loading", "Loading recipes"),
    event("error", { error: { code: "PLAN_INFEASIBLE", message: "No feasible plan after all relaxations", details: [] } }),
  ]));
  await assert.rejects(generatePlan(request), /No plan fits these settings/);

  fetchMock.mock.mockImplementation(async () => stream([
    event("error", { error: { code: "SOMETHING_NEW", message: "Neo4j is warming up", details: [] } }),
  ]));
  await assert.rejects(generatePlan(request), /Neo4j is warming up/);
});

test("a stream that ends early or sends a bad plan is reported", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => stream([progress(1, "loading", "Loading recipes")]));
  await assert.rejects(generatePlan(request), /stopped before the plan was ready/);
  fetchMock.mock.mockImplementation(async () => stream([event("plan", { status: "complete" })]));
  await assert.rejects(generatePlan(request), /unexpected response/);
  fetchMock.mock.mockImplementation(async () => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(progress(1, "loading", "Loading recipes")));
      controller.error(new TypeError("network dropped"));
    },
  }), { headers: { "content-type": "text/event-stream" } }));
  await assert.rejects(generatePlan(request), /connection to the meal planner was lost/);
});

test("nutrient keys from totals and meals map to labels and units", () => {
  assert.deepEqual(
    [nutrientInfo("avg_daily_protein_g"), nutrientInfo("calories"), nutrientInfo("avg_daily_vitamin_c_mg")]
      .map(({ label, unit }) => [label, unit]),
    [["Protein", "g"], ["Calories", "kcal"], ["Vitamin c", "mg"]],
  );
  assert.equal(formatNutrient("avg_daily_sodium_mg", 1234.56), "1,234.6 mg");
  assert.deepEqual(
    sortedNutrients({ fat_g: 1, unknown_g: 2, calories: 3, protein_g: 4 }).map(([key]) => key),
    ["calories", "protein_g", "fat_g", "unknown_g"],
  );
});

test("ingredients and relaxations read as plain sentences", () => {
  assert.equal(
    formatIngredient({ quantity: 200, unit: "g", text: "canned chickpeas", preparation: "drained", optional: false }),
    "200 g canned chickpeas, drained",
  );
  assert.equal(
    formatIngredient({ quantity: 0.3333, unit: null, text: "lemon", preparation: null, optional: true }),
    "0.33 lemon",
  );
  assert.equal(
    formatIngredient({ quantity: null, unit: null, text: null, preparation: null, optional: false }),
    "Unnamed ingredient",
  );
  assert.equal(
    describeRelaxation({ stage: 1, kind: "extra_days_per_recipe", detail: { added: 1 } }),
    "Let each recipe repeat on 1 more day.",
  );
  assert.equal(
    describeRelaxation({ stage: 3, kind: "widen_nutrient_max", detail: { nutrients: [{ code: "protein", from: 120000, to: 132000 }] } }),
    "Raised the daily maximum for protein from 120 to 132 g.",
  );
});
