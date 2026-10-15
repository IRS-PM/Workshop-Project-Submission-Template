import { Bookmark } from "@/components/icons";
import {
  describeRelaxation,
  formatIngredient,
  formatNutrient,
  nutrientInfo,
  sortedNutrients,
  type PlanMeal,
  type PlanResponse,
} from "@/lib/plan-api";

const HEADLINE = new Set(["calories", "protein_g", "carbs_g", "fat_g"]);

export default function PlanView({ plan, servings, overview }: { plan: PlanResponse; servings: number; overview?: string }) {
  const totals = sortedNutrients(plan.horizon_totals);
  const complete = plan.status === "complete";
  const unverified = Object.values(plan.validation_summary).includes("unverified");

  return (
    <section aria-labelledby="plan-heading" className="mt-12 border-t border-subtle pt-10">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="plan-heading" className="text-3xl font-extrabold tracking-tight">
          Your {plan.days.length}-day plan
        </h2>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold ${
            complete ? "bg-sage text-sage-foreground" : "bg-accent/10 text-accent"
          }`}
        >
          {unverified ? "Unverified restrictions" : complete ? "Complete" : "Adjusted to fit"}
        </span>
      </div>
      <p className="mt-2 text-sm text-muted">
        {plan.message}
        {servings > 1 && ` Amounts are for ${servings} servings.`}
      </p>
      {unverified && (
        <p role="alert" className="mt-4 rounded-2xl border border-accent bg-accent/10 p-4 text-sm font-semibold">
          Allergy/dietary restrictions are unverified. Known conflicts were screened out,
          but missing evidence is not proof of safety. This plan is not guaranteed allergy-safe
          or diet-compliant; check every ingredient and product label.
        </p>
      )}
      {overview?.trim() && (
        <p className="mt-4 whitespace-pre-line text-sm leading-relaxed">{overview.trim()}</p>
      )}

      {plan.relaxations.length > 0 && (
        <div className="mt-5 rounded-2xl bg-cream p-4 text-sm">
          <p className="font-bold">To make everything fit, the planner:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
            {plan.relaxations.map((relaxation) => (
              <li key={`${relaxation.stage}-${relaxation.kind}`}>{describeRelaxation(relaxation)}</li>
            ))}
          </ul>
        </div>
      )}

      {totals.length > 0 && (
        <>
          <h3 className="mt-8 text-sm font-bold">Average per day</h3>
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {totals.map(([key, value]) => (
              <div key={key} className="rounded-2xl bg-sage/50 p-4">
                <dt className="text-xs font-semibold text-muted">{nutrientInfo(key).label}</dt>
                <dd className="mt-1 text-lg font-bold tabular-nums">{formatNutrient(key, value)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      <ol className="mt-10 space-y-10">
        {plan.days.map((day) => (
          <li key={day.day}>
            <h3 className="eyebrow">Day {day.day}</h3>
            <ul className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {day.meals.map((meal) => (
                <MealCard key={meal.slot} meal={meal} />
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}

type MealCardProps = {
  meal: PlanMeal;
  label?: string;
  /** Shows a bookmark on the card. */
  saved?: boolean;
  /** Given, the card becomes a button that opens the meal's details, and the
   *  ingredients and method move into that pop-up. */
  onOpen?: () => void;
  /** Controls under the card, outside the button, such as like buttons. */
  footer?: React.ReactNode;
};

export function MealCard({ meal, label, saved = false, onOpen, footer }: MealCardProps) {
  const headline = sortedNutrients(meal.nutrients).filter(([key]) => HEADLINE.has(key));

  const summary = (
    <>
      <p className="flex items-center justify-between gap-2 text-xs font-semibold text-muted">
        {label ?? meal.slot.replace(/^meal_/, "Meal ")}
        {saved && (
          <span className="text-accent">
            <Bookmark filled className="size-4" />
            <span className="sr-only">Saved</span>
          </span>
        )}
      </p>
      <h4 className="mt-1 font-bold leading-snug">{meal.title}</h4>
      {headline.length > 0 && (
        <p className="mt-1.5 text-sm text-muted tabular-nums">
          {headline
            .map(([key, value]) =>
              key === "calories"
                ? formatNutrient(key, value)
                : `${formatNutrient(key, value)} ${nutrientInfo(key).label.toLowerCase()}`,
            )
            .join(" · ")}
        </p>
      )}
    </>
  );

  if (onOpen) {
    return (
      <li className="flex flex-col rounded-2xl border border-subtle bg-surface transition hover:-translate-y-0.5 hover:border-sage-deep hover:shadow-[0_12px_28px_-14px_rgba(33,56,42,0.25)]">
        <button type="button" onClick={onOpen} className="flex flex-1 flex-col rounded-2xl p-4 text-left">
          {summary}
          <span className="mt-auto pt-3 text-sm font-semibold text-accent">View details</span>
        </button>
        {footer && <div className="-mt-1 px-4 pb-4">{footer}</div>}
      </li>
    );
  }

  return (
    <li className="flex flex-col rounded-2xl border border-subtle bg-surface p-4">
      {summary}

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-semibold text-accent">Ingredients &amp; method</summary>
        {meal.ingredients.length > 0 && (
          <ul className="mt-3 space-y-1">
            {meal.ingredients.map((ingredient, index) => (
              <li key={index} className="leading-snug">
                {formatIngredient(ingredient)}
                {ingredient.optional && <span className="text-muted"> (optional)</span>}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 whitespace-pre-line leading-relaxed text-muted">
          {meal.instructions?.trim() || "No method available for this recipe."}
        </p>
      </details>
    </li>
  );
}
