"use client";

import { useEffect, useRef } from "react";
import { Bookmark, Close } from "@/components/icons";
import { formatIngredient, formatNutrient, nutrientInfo, sortedNutrients, type PlanMeal } from "@/lib/plan-api";

type Props = {
  /** The meal to show; null keeps the pop-up closed. */
  meal: PlanMeal | null;
  label?: string;
  saved: boolean;
  saving: boolean;
  error: string | null;
  onToggleSave: () => void;
  onClose: () => void;
  /** Like buttons, shown under the title. */
  rating?: React.ReactNode;
};

/** A meal's full details in a modal. Built on <dialog>, so Escape, focus
 *  trapping and the backdrop come from the browser. */
export default function MealDialog({ meal, label, saved, saving, error, onToggleSave, onClose, rating }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (meal && !dialog.open) dialog.showModal();
    if (!meal && dialog.open) dialog.close();
  }, [meal]);

  const nutrients = meal ? sortedNutrients(meal.nutrients) : [];

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // The inner panel fills the dialog, so a click landing on the dialog
      // itself can only be on the backdrop.
      onClick={(event) => {
        if (event.target === event.currentTarget) ref.current?.close();
      }}
      aria-labelledby="meal-dialog-title"
      className="m-auto max-h-[85vh] w-[min(40rem,calc(100%-2rem))] overflow-hidden rounded-3xl border border-subtle bg-surface p-0 text-foreground shadow-[0_24px_60px_-20px_rgba(33,56,42,0.45)] backdrop:bg-foreground/40"
    >
      {meal && (
        <div className="max-h-[85vh] overflow-y-auto p-6 sm:p-7">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              {label && <p className="eyebrow">{label}</p>}
              <h2 id="meal-dialog-title" className="mt-1 text-2xl font-extrabold leading-tight tracking-tight">
                {meal.title}
              </h2>
            </div>

            <button
              type="button"
              onClick={onToggleSave}
              disabled={saving}
              aria-pressed={saved}
              aria-label={saved ? "Remove from saved meals" : "Save meal"}
              title={saved ? "Remove from saved meals" : "Save meal"}
              className={`grid size-10 shrink-0 place-items-center rounded-full transition disabled:cursor-wait disabled:opacity-60 ${
                saved ? "bg-accent text-accent-foreground hover:opacity-90" : "bg-cream text-foreground hover:bg-sage"
              }`}
            >
              <Bookmark filled={saved} className="size-5" />
            </button>
            <button
              type="button"
              onClick={() => ref.current?.close()}
              aria-label="Close"
              className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition hover:bg-cream hover:text-foreground"
            >
              <Close className="size-5" />
            </button>
          </div>

          <p role="status" className={`mt-2 min-h-5 text-sm ${error ? "text-accent" : "text-muted"}`}>
            {error ?? (saving ? (saved ? "Removing…" : "Saving…") : saved ? "Saved to your meals." : "")}
          </p>

          {rating && (
            <div className="mt-3 flex items-center gap-3">
              <span className="text-sm font-semibold">Did you like it?</span>
              {rating}
            </div>
          )}

          {nutrients.length > 0 && (
            <>
              <h3 className="mt-4 text-sm font-bold">Nutrition</h3>
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {nutrients.map(([key, value]) => (
                  <div key={key} className="rounded-2xl bg-sage/50 p-3">
                    <dt className="text-xs font-semibold text-muted">{nutrientInfo(key).label}</dt>
                    <dd className="mt-0.5 font-bold tabular-nums">{formatNutrient(key, value)}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}

          <h3 className="mt-6 text-sm font-bold">Ingredients</h3>
          {meal.ingredients.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {meal.ingredients.map((ingredient, index) => (
                <li key={index} className="leading-snug">
                  {formatIngredient(ingredient)}
                  {ingredient.optional && <span className="text-muted"> (optional)</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">No ingredient list for this recipe.</p>
          )}

          <h3 className="mt-6 text-sm font-bold">Method</h3>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
            {meal.instructions?.trim() || "No method available for this recipe."}
          </p>
        </div>
      )}
    </dialog>
  );
}
