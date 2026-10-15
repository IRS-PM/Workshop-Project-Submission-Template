"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Chip from "@/components/chip";
import FormError from "@/components/form-error";
import PlanView from "@/components/plan-view";
import { Close, Plus } from "@/components/icons";
import { ApiError, loadPreferences } from "@/lib/api";
import {
  ALLERGENS,
  DIETARY,
  PLAN_NUTRIENTS,
  generatePlan,
  type AllergenCode,
  type DietaryCode,
  type NutrientCode,
  type NutrientTarget,
  type PlanProgress,
  type PlanRequest,
  type PlanResponse,
} from "@/lib/plan-api";

type TargetRow = { id: number; code: NutrientCode; goal: string; min: string; max: string };

const PREFERRED_TARGETS: Record<string, Omit<TargetRow, "id">> = {
  Protein: { code: "protein", goal: "", min: "50", max: "" },
  Fibre: { code: "fiber", goal: "", min: "28", max: "" },
  "Lower sodium": { code: "sodium", goal: "", min: "", max: "2300" },
  "Lower sugar": { code: "sugar", goal: "", min: "", max: "50" },
};

const fieldsetClass = "rounded-3xl border border-subtle bg-surface p-6";
const controlClass = "mt-1.5 w-full rounded-xl border border-subtle bg-surface px-3 py-2.5 text-sm font-normal outline-none focus:border-accent focus:ring-2 focus:ring-accent/20";

const unitOf = (code: NutrientCode) => PLAN_NUTRIENTS.find((item) => item.code === code)?.unit ?? "";

const toggle = <T,>(list: T[], value: T) =>
  list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

function toTarget(row: TargetRow): NutrientTarget {
  const read = (value: string) => (value.trim() === "" ? undefined : Number(value));
  const [goal, min, max] = [read(row.goal), read(row.min), read(row.max)];
  const target: NutrientTarget = { code: row.code, unit: unitOf(row.code) };
  if (goal !== undefined) target.goal = { value: goal };
  if (min !== undefined || max !== undefined) target.limit = { min, max };
  return target;
}

export default function PlanBuilder() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [prefilled, setPrefilled] = useState(false);
  const [days, setDays] = useState("7");
  const [meals, setMeals] = useState("3");
  const [servings, setServings] = useState("1");
  const [dietary, setDietary] = useState<DietaryCode[]>([]);
  const [allergies, setAllergies] = useState<AllergenCode[]>([]);
  const [targets, setTargets] = useState<TargetRow[]>([]);
  const [pending, setPending] = useState(false);
  const [progress, setProgress] = useState<PlanProgress | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<{ response: PlanResponse; servings: number } | null>(null);
  const nextId = useRef(0);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    loadPreferences()
      .then((stored) => {
        if (cancelled || !stored) return;
        const diet = stored.special_diet;
        const preferred = stored.preferred_nutrient ? PREFERRED_TARGETS[stored.preferred_nutrient] : undefined;
        if (diet === "halal" || diet === "vegetarian") setDietary([diet]);
        if (preferred) setTargets([{ id: nextId.current++, ...preferred }]);
        setPrefilled(diet === "halal" || diet === "vegetarian" || preferred !== undefined);
      })
      .catch((caught) => {
        if (!cancelled && caught instanceof ApiError && caught.status === 401) {
          router.push("/signin");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (plan) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [plan]);

  function addTarget() {
    const unused = PLAN_NUTRIENTS.find((item) => !targets.some((row) => row.code === item.code));
    if (!unused) return;
    const id = nextId.current++;
    setTargets((current) => [...current, { id, code: unused.code, goal: "", min: "", max: "" }]);
  }

  function updateTarget(id: number, patch: Partial<Omit<TargetRow, "id">>) {
    setTargets((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;

    const request: PlanRequest = {
      horizon_days: Number(days),
      meals_per_day: Number(meals),
      servings: Number(servings),
      ...(allergies.length ? { allergies: allergies.map((code) => ({ code })) } : {}),
      ...(dietary.length ? { dietary: dietary.map((code) => ({ code })) } : {}),
      ...(targets.length ? { nutrients: targets.map(toTarget) } : {}),
    };

    setError(null);
    setPlan(null);
    setProgress(null);
    setText("");
    setPending(true);
    try {
      const response = await generatePlan(request, {
        onProgress: setProgress,
        onText: (chunk) => setText((current) => current + chunk),
      });
      setPlan({ response, servings: request.servings });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not build a plan.");
    } finally {
      setPending(false);
    }
  }

  if (loading) {
    return (
      <div className="mt-8 space-y-6" aria-busy="true">
        {[0, 1, 2].map((index) => (
          <div key={index} className="h-36 animate-pulse rounded-3xl border border-subtle bg-surface/60" />
        ))}
      </div>
    );
  }

  return (
    <>
      <form onSubmit={submit} className="mt-8" aria-busy={pending}>
        <fieldset disabled={pending} className="min-w-0 space-y-6 disabled:opacity-60">
          {prefilled && (
            <p className="rounded-2xl bg-sage/60 px-4 py-3 text-sm text-sage-foreground">
              Filled in from your preferences. Changes here only apply to this plan.
            </p>
          )}

          <fieldset className={fieldsetClass}>
            <legend className="float-left w-full text-sm font-bold">Plan size</legend>
            <p className="clear-both text-sm text-muted">How far ahead, and how many people you&rsquo;re feeding.</p>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <label htmlFor="plan-days" className="text-sm font-semibold">
                Days
                <input id="plan-days" type="number" min="1" max="14" step="1" required value={days} onChange={(event) => setDays(event.target.value)} className={controlClass} />
              </label>
              <label htmlFor="plan-meals" className="text-sm font-semibold">
                Meals a day
                <input id="plan-meals" type="number" min="1" max="6" step="1" required value={meals} onChange={(event) => setMeals(event.target.value)} className={controlClass} />
              </label>
              <label htmlFor="plan-servings" className="text-sm font-semibold">
                Servings
                <input id="plan-servings" type="number" min="1" step="1" required value={servings} onChange={(event) => setServings(event.target.value)} className={controlClass} />
              </label>
            </div>
          </fieldset>

          <fieldset className={fieldsetClass}>
            <legend className="float-left w-full text-sm font-bold">Diet</legend>
            <p className="clear-both text-sm text-muted">Leave both off if anything goes.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {DIETARY.map(({ code, label }) => (
                <Chip key={code} label={label} selected={dietary.includes(code)} onClick={() => setDietary((current) => toggle(current, code))} />
              ))}
            </div>
          </fieldset>

          <fieldset className={fieldsetClass}>
            <legend className="float-left w-full text-sm font-bold">Allergies</legend>
            <p className="clear-both text-sm text-muted">Anything the plan should avoid.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {ALLERGENS.map(({ code, label }) => (
                <Chip key={code} label={label} selected={allergies.includes(code)} onClick={() => setAllergies((current) => toggle(current, code))} />
              ))}
            </div>
          </fieldset>

          <fieldset className={fieldsetClass}>
            <legend className="float-left w-full text-sm font-bold">Daily nutrient targets</legend>
            <p className="clear-both text-sm text-muted">Per person, per day. Set a target, a range, or both.</p>

            {targets.length === 0 ? (
              <p className="mt-4 text-sm text-muted">No targets yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {targets.map((row) => {
                  const unit = unitOf(row.code);
                  return (
                    <li key={row.id} className="grid grid-cols-3 items-end gap-3 rounded-2xl border border-subtle p-4 sm:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(0,1fr))_auto]">
                      <label htmlFor={`target-${row.id}-code`} className="col-span-2 text-sm font-semibold sm:col-span-1">
                        Nutrient
                        <select
                          id={`target-${row.id}-code`}
                          value={row.code}
                          onChange={(event) => updateTarget(row.id, { code: event.target.value as NutrientCode })}
                          className={controlClass}
                        >
                          {PLAN_NUTRIENTS.map((item) => (
                            <option key={item.code} value={item.code} disabled={targets.some((other) => other.id !== row.id && other.code === item.code)}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        onClick={() => setTargets((current) => current.filter((item) => item.id !== row.id))}
                        aria-label={`Remove ${PLAN_NUTRIENTS.find((item) => item.code === row.code)?.label ?? "target"}`}
                        className="grid size-10 place-items-center justify-self-end rounded-full text-muted transition hover:bg-cream hover:text-foreground sm:order-last"
                      >
                        <Close className="size-5" />
                      </button>
                      {(["goal", "min", "max"] as const).map((field) => (
                        <label key={field} htmlFor={`target-${row.id}-${field}`} className="text-sm font-semibold">
                          {field === "goal" ? "Target" : field === "min" ? "Min" : "Max"}{" "}
                          <span className="font-normal text-muted">({unit})</span>
                          <input
                            id={`target-${row.id}-${field}`}
                            type="number"
                            min="0"
                            step="any"
                            inputMode="decimal"
                            value={row[field]}
                            onChange={(event) => updateTarget(row.id, { [field]: event.target.value })}
                            className={controlClass}
                          />
                        </label>
                      ))}
                    </li>
                  );
                })}
              </ul>
            )}

            <button
              type="button"
              onClick={addTarget}
              disabled={targets.length === PLAN_NUTRIENTS.length}
              className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-subtle px-4 py-2 text-sm font-semibold text-muted transition hover:border-sage-deep hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="size-4" />
              Add a target
            </button>
          </fieldset>

          <FormError message={error} />

          <button
            type="submit"
            className="rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {pending ? "Building your plan…" : "Build my plan"}
          </button>
        </fieldset>
      </form>

      {pending && (
        <p role="status" className="mt-4 text-sm text-muted">
          {progress ? `${progress.message}… (step ${progress.step} of ${progress.total})` : "Starting…"}
        </p>
      )}

      {pending && text && (
        <p aria-live="polite" className="mt-4 whitespace-pre-line rounded-2xl border border-subtle bg-surface p-4 text-sm leading-relaxed">
          {text.trim()}
        </p>
      )}

      <div ref={resultRef} className="scroll-mt-6">
        {plan && <PlanView plan={plan.response} servings={plan.servings} overview={text} />}
      </div>
    </>
  );
}
