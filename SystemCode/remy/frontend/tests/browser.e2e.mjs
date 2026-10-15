import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { chromium } from "playwright";

// Real Docker services + real food graph. Never send synthetic grades as human judgments.
process.loadEnvFile(fileURLToPath(new URL("../../../.env.nonprod", import.meta.url)));
const base = process.env.E2E_FRONTEND_URL ?? "http://localhost:3100";
const api = process.env.E2E_API_URL ?? "http://localhost:8003";
const langfuse = `http://localhost:${process.env.LANGFUSE_PORT}`;
const artifactDir = fileURLToPath(new URL("../../../target/e2e/", import.meta.url));
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test("browser signup, preferences, login, streamed meal plan, and Langfuse trace", { timeout: 240_000 }, async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.__e2ePlan = null;
    window.fetch = async (...args) => {
      if (String(args[0]).endsWith("/api/v1/plan")) window.__e2ePlan = null;
      const response = await original(...args);
      if (String(args[0]).endsWith("/api/v1/plan") && response.ok) {
        response.clone().text().then((body) => {
          for (const block of body.split("\n\n")) {
            if (block.startsWith("event: plan\n")) {
              window.__e2ePlan = JSON.parse(block.split("data: ")[1]);
            }
          }
        });
      }
      return response;
    };
  });
  const username = "e2e_" + randomBytes(6).toString("hex");
  const password = randomBytes(24).toString("base64url");
  try {
    await page.goto(base + "/signup");
    await page.getByLabel("Username", { exact: true }).fill(username);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.waitForURL("**/welcome");
    await page.getByText("Meat", { exact: true }).click();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByRole("button", { name: "Chinese", exact: true }).click();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByRole("button", { name: "Start cooking", exact: true }).click();
    await page.waitForURL(base + "/");
    const cookie = (await context.cookies()).find((item) => item.name === "remy_workshop_session");
    assert(cookie?.httpOnly, "Authentication must use an HttpOnly cookie");

    await page.getByRole("button", { name: "Log out", exact: true }).click();
    await page.waitForURL("**/signin");
    await page.getByLabel("Username", { exact: true }).fill(username);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL(base + "/");
    await page.goto(base + "/preferences");
    await page.getByRole("heading", { name: "What do you eat?" }).waitFor();
    const prefs = await context.request.get("http://localhost:8010/preferences");
    assert.equal(prefs.status(), 200);
    assert.equal((await prefs.json()).special_diet, "meat");

    await page.goto(base + "/plan");
    await page.getByLabel("Days", { exact: true }).fill("1");
    await page.getByLabel("Meals a day", { exact: true }).fill("1");
    await page.getByRole("button", { name: "Add a target", exact: true }).click();
    await page.getByLabel("Target (kcal)", { exact: true }).fill("600");
    await page.getByRole("button", { name: "Build my plan", exact: true }).click();
    await page.getByRole("heading", { name: "Your 1-day plan", exact: true }).waitFor({ timeout: 90_000 });
    await page.waitForFunction(() => window.__e2ePlan !== null);
    const plan = await page.evaluate(() => window.__e2ePlan);
    assert(plan.trace_id && plan.evaluation_id, "Streaming must preserve monitoring IDs");
    assert.equal(plan.days.length, 1);
    assert.equal(plan.days[0].meals.length, 1);
    assert.equal(await page.locator("#plan-heading").textContent(), "Your 1-day plan");
    await page.getByText("Ingredients & method", { exact: true }).click();
    assert.equal(pageErrors.length, 0, "Browser runtime errors: " + pageErrors.join("; "));
    await mkdir(artifactDir, { recursive: true });
    await page.screenshot({ path: artifactDir + "meal-plan.png", fullPage: true });

    const snapshot = await fetch(api + "/api/v1/evaluations/" + plan.evaluation_id, {
      headers: { Authorization: "Bearer " + process.env.REMY_EVALUATION_TOKEN },
    });
    assert.equal(snapshot.status, 200);
    assert((await snapshot.json()).candidates.length > 0);
    const auth = "Basic " + Buffer.from(`${process.env.LANGFUSE_PUBLIC_KEY}:${process.env.LANGFUSE_SECRET_KEY}`).toString("base64");
    const stages = ["meal-plan", "retrieve-candidates", "filter-candidates", "rank-candidates", "solve-plan", "generate-response"];
    let trace;
    for (let attempt = 0; attempt < 60; attempt++) {
      const response = await fetch(langfuse + "/api/public/traces/" + plan.trace_id, { headers: { Authorization: auth } });
      if (response.ok) {
        trace = await response.json();
        if (stages.every((stage) => trace.observations?.some((span) => span.name === stage))) break;
      }
      await pause(2000);
    }
    assert(stages.every((stage) => trace?.observations?.some((span) => span.name === stage)), "Stream stage traces missing");
    const dashboard = await context.request.get(langfuse + "/api/auth/session");
    assert.equal((await dashboard.json()).user.email, process.env.LANGFUSE_INIT_USER_EMAIL);
    const restrictedTraces = [];
    for (const restriction of ["Halal", "Vegetarian", "Peanuts"]) {
      await page.goto(base + "/plan");
      await page.getByLabel("Days", { exact: true }).fill("1");
      await page.getByLabel("Meals a day", { exact: true }).fill("1");
      await page.getByText(restriction, { exact: true }).click();
      await page.getByRole("button", { name: "Build my plan", exact: true }).click();
      await page.getByRole("alert").filter({ hasText: "restrictions are unverified" }).waitFor({ timeout: 90_000 });
      await page.waitForFunction(() => window.__e2ePlan !== null);
      const result = await page.evaluate(() => window.__e2ePlan);
      assert.equal(result.status, "partial");
      assert(Object.values(result.validation_summary).includes("unverified"));
      assert(result.trace_id && result.trace_id !== plan.trace_id);
      assert.equal(result.days[0].meals.length, 1);
      restrictedTraces.push({ restriction, trace_id: result.trace_id });
    }
    assert.equal(pageErrors.length, 0, "Browser runtime errors: " + pageErrors.join("; "));
    await page.screenshot({ path: artifactDir + "restricted-meal-plan.png", fullPage: true });
    await writeFile(artifactDir + "result.json", JSON.stringify({
      webapp: base, trace_id: plan.trace_id, evaluation_id: plan.evaluation_id,
      stages, restricted_traces: restrictedTraces, meal: plan.days[0].meals[0].title, human_grades: "pending",
    }, null, 2));
    console.log(`E2E passed: ${base}; unrestricted + Halal + Vegetarian + Peanuts plans rendered; six Langfuse stages; human grades pending.`);
  } finally {
    await browser.close();
  }
});
