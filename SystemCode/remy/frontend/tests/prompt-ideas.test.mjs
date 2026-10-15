import assert from "node:assert/strict";
import { test } from "node:test";
import {
  NO_CONSTRAINTS,
  describeConstraints,
  fromPreferences,
  ideaRequest,
  mergeConstraints,
  readPrompt,
  replyFor,
  uniqueIdeas,
} from "../src/lib/prompt-ideas.ts";

test("prompts map to diet, nutrient goals, and allergies", () => {
  assert.deepEqual(readPrompt("Plant-powered").found, { dietary: ["vegetarian"], allergies: [], goals: {} });
  assert.deepEqual(readPrompt("Protein please").found.goals, { protein: 40 });
  assert.deepEqual(readPrompt("Something light, halal, no dairy or eggs").found, {
    dietary: ["halal"],
    allergies: ["milk", "egg"],
    goals: { calories: 450 },
  });
  assert.deepEqual(readPrompt("gluten-free and low sugar").found, { dietary: [], allergies: ["wheat"], goals: { sugar: 5 } });
  assert.deepEqual(readPrompt("eggplant without fuss").found.allergies, []);
});

test("unsupported asks and resets are recognised", () => {
  const quick = readPrompt("Ready in 20, something spicy and Thai");
  assert.deepEqual(quick.unsupported, ["cooking time", "cuisine", "flavour"]);
  assert.equal(quick.understood, false);
  assert.equal(readPrompt("Surprise me").reset, true);
  assert.equal(readPrompt("More protein").understood, true);
});

test("follow-ups build on earlier constraints and preferences", () => {
  const base = fromPreferences({ special_diet: "halal", preferred_nutrient: "Protein" });
  assert.deepEqual(base, { dietary: ["halal"], allergies: [], goals: { protein: 40 } });
  assert.deepEqual(fromPreferences({ special_diet: "meat", preferred_nutrient: null }), NO_CONSTRAINTS);
  const merged = mergeConstraints(mergeConstraints(base, readPrompt("No dairy").found), readPrompt("make it filling").found);
  assert.deepEqual(merged, { dietary: ["halal"], allergies: ["milk"], goals: { protein: 40, calories: 900 } });
  assert.deepEqual(describeConstraints(merged), ["halal", "high protein", "filling", "no dairy"]);
});

test("idea requests ask the planner for three single-meal days", () => {
  assert.deepEqual(ideaRequest({ dietary: ["vegetarian"], allergies: ["milk"], goals: { protein: 40 } }), {
    horizon_days: 3,
    meals_per_day: 1,
    servings: 1,
    dietary: [{ code: "vegetarian" }],
    allergies: [{ code: "milk" }],
    nutrients: [{ code: "protein", unit: "g", goal: { value: 40 } }],
  });
  assert.deepEqual(ideaRequest(NO_CONSTRAINTS, () => 0.5).nutrients, [{ code: "calories", unit: "kcal", goal: { value: 800 } }]);
});

const meal = (recipe_id, title) => ({ slot: "meal_1", recipe_id, title, nutrients: {}, ingredients: [], instructions: null });

test("ideas are de-duplicated and the reply explains what was used", () => {
  const plan = { days: [{ day: 1, meals: [meal("r1", "A")] }, { day: 2, meals: [meal("r2", "B")] }, { day: 3, meals: [meal("r1", "A")] }] };
  const ideas = uniqueIdeas(plan);
  assert.deepEqual(ideas.map((idea) => idea.recipe_id), ["r1", "r2"]);

  const vegetarian = { dietary: ["vegetarian"], allergies: [], goals: { protein: 40 } };
  const reply = replyFor(ideas, vegetarian, readPrompt("vegetarian, quick"));
  assert.equal(reply.text, "Here are 2 ideas for vegetarian and high protein. I can't filter by cooking time yet.");
  assert.match(reply.note, /check the ingredients/);

  const vague = replyFor([meal("r3", "C")], NO_CONSTRAINTS, readPrompt("hmm, anything nice?"));
  assert.equal(vague.text, "Here's 1 idea. Try words like “vegetarian”, “no dairy” or “more protein” to steer me.");
  assert.equal(vague.note, undefined);
  assert.equal(replyFor([], NO_CONSTRAINTS, readPrompt("Surprise me")).text, "I couldn't find anything that fits that.");
});
