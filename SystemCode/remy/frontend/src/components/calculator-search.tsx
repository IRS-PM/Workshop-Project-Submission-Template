"use client";

import { useState, type FormEvent } from "react";
import { calculateIngredient, type CalculationResponse, type IngredientUnit, type Nutrients } from "@/lib/calculator-api";
import { normalizeIngredientName } from "@/lib/ingredient-normalization";

const NUTRIENTS: [keyof Nutrients, string, string][] = [
  ["calories_kcal", "Energy", "kcal"],
  ["protein_g", "Protein", "g"],
  ["carbs_g", "Carbohydrates", "g"],
  ["fat_g", "Fat", "g"],
  ["fiber_g", "Fiber", "g"],
  ["sugar_g", "Sugar", "g"],
  ["sodium_mg", "Sodium", "mg"],
];
const money = (value: number | null) => value == null ? "Unavailable" : `S$${value.toFixed(2)}`;
const amount = (value: number | null, unit: string) => value == null ? "Unavailable" : `${value} ${unit}`;
const controlClass = "mt-1.5 w-full rounded-xl border border-subtle bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

export default function CalculatorSearch() {
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("100");
  const [unit, setUnit] = useState<IngredientUnit>("g");
  const [servings, setServings] = useState("1");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CalculationResponse | null>(null);
  const normalizedName = normalizeIngredientName(name);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setError("");
    setResult(null);
    setPending(true);
    try {
      setResult(await calculateIngredient({
        servings: Number(servings),
        ingredients: [{ name: normalizedName, quantity: Number(quantity), unit }],
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to calculate this ingredient.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="calculator-heading" className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6">
      <h2 id="calculator-heading" className="text-lg font-bold">Check an ingredient</h2>
      <p className="mt-1 text-sm text-muted">Find its nutrition and the cost of what you use.</p>

      <form onSubmit={submit} className="mt-5" aria-busy={pending}>
        <fieldset disabled={pending} className="min-w-0 space-y-4 disabled:opacity-60">
          <div>
            <label htmlFor="calculator-ingredient" className="text-sm font-semibold">Ingredient name</label>
            <div className="mt-1.5 flex flex-col gap-2 sm:flex-row">
              <input
                id="calculator-ingredient"
                type="search"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Fresh chopped tomatoes"
                required
                maxLength={200}
                aria-describedby="calculator-normalized"
                className="min-w-0 flex-1 rounded-xl border border-subtle px-4 py-3 outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
              <button type="submit" disabled={!normalizedName || pending} className="rounded-xl bg-accent px-5 py-3 text-sm font-bold text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
                {pending ? "Calculating…" : "Calculate"}
              </button>
            </div>
            <p id="calculator-normalized" className="mt-2 text-xs text-muted" aria-live="polite">
              {normalizedName ? <>Searching for: <span className="font-semibold text-foreground">{normalizedName}</span></> : name.trim() ? "Add an ingredient name after the preparation words." : "Enter one ingredient; set the amount below."}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <label htmlFor="calculator-quantity" className="text-sm font-semibold">
              Quantity
              <input id="calculator-quantity" type="number" min="0" step="any" required value={quantity} onChange={(event) => setQuantity(event.target.value)} className={controlClass} />
            </label>
            <label htmlFor="calculator-unit" className="text-sm font-semibold">
              Unit
              <select id="calculator-unit" value={unit} onChange={(event) => setUnit(event.target.value as IngredientUnit)} className={controlClass}>
                <option value="g">Grams (g)</option>
                <option value="kg">Kilograms (kg)</option>
                <option value="ml">Millilitres (ml)</option>
                <option value="tbsp">Tablespoons</option>
                <option value="pc">Pieces</option>
              </select>
            </label>
            <label htmlFor="calculator-servings" className="text-sm font-semibold">
              Servings
              <input id="calculator-servings" type="number" min="1" max="1000" step="1" required value={servings} onChange={(event) => setServings(event.target.value)} className={controlClass} />
            </label>
          </div>
        </fieldset>
      </form>

      {pending && <p role="status" className="mt-4 text-sm text-muted">Looking up nutrition and grocery prices…</p>}
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      {result && (
        <div className="mt-6 border-t border-subtle pt-5" aria-live="polite">
          <h3 className="font-bold">Results for {result.itemized.map((item) => item.canonical_name).join(", ")}</h3>
          <p className="mt-1 text-sm text-muted">{result.itemized.map((item) => amount(item.consumed_amount_g, "g")).join(" + ")} · {result.servings} {result.servings === 1 ? "serving" : "servings"}</p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-sage/50 p-4">
              <dt className="text-xs font-semibold text-muted">Cost of amount used</dt>
              <dd className="mt-1 text-xl font-bold">{money(result.summary.total_consumed_cost_sgd)}</dd>
            </div>
            <div className="rounded-2xl bg-cream p-4">
              <dt className="text-xs font-semibold text-muted">Whole packages to buy</dt>
              <dd className="mt-1 text-xl font-bold">{money(result.summary.total_retail_package_cost_sgd)}</dd>
            </div>
          </dl>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Total and per-serving nutrition</caption>
              <thead><tr className="border-b border-subtle text-muted"><th scope="col" className="py-2 font-medium">Nutrient</th><th scope="col" className="py-2 text-right font-medium">Total</th><th scope="col" className="py-2 text-right font-medium">Per serving</th></tr></thead>
              <tbody>{NUTRIENTS.map(([key, label, nutrientUnit]) => (
                <tr key={key} className="border-b border-subtle/60">
                  <th scope="row" className="py-2 font-medium">{label}</th>
                  <td className="py-2 text-right tabular-nums">{amount(result.summary.nutrients[key], nutrientUnit)}</td>
                  <td className="py-2 text-right tabular-nums">{amount(result.summary.nutrients_per_serving[key], nutrientUnit)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {result.itemized.map((item, index) => (
            <div key={index} className="mt-3 space-y-2 text-sm">
              {item.matched_package && <p className="text-muted">{item.matched_package.package_title ?? "Matched package"}{item.matched_package.retailer ? ` · ${item.matched_package.retailer}` : ""}{item.matched_package.package_count != null ? ` · ${item.matched_package.package_count} package(s)` : ""}</p>}
              {item.warnings.map((warning, warningIndex) => <p key={`${warning.code}-${warningIndex}`} className="rounded-xl bg-cream px-3 py-2 text-muted">{warning.message}</p>)}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
