"use client";

import { useState } from "react";
import { Check, Clock, Close } from "@/components/icons";
import LikeButtons from "@/components/like-buttons";
import MealDialog from "@/components/meal-dialog";
import type { PlanMeal } from "@/lib/plan-api";
import { useRatings } from "@/lib/use-ratings";
import { useSavedMeals } from "@/lib/use-saved-meals";

const DATE = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export default function RatingHistory() {
  const ratings = useRatings();
  const saved = useSavedMeals();
  const [open, setOpen] = useState<PlanMeal | null>(null);

  if (ratings.ratings === null) {
    return <p className="mt-8 animate-pulse text-sm text-muted">Loading your history…</p>;
  }

  return (
    <>
      {ratings.loadError && <p className="mt-6 text-sm text-accent">{ratings.loadError}</p>}

      {ratings.ratings.length === 0 ? (
        <div className="mt-8 rounded-3xl border border-dashed border-subtle bg-surface/60 px-6 py-16 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-cream text-muted">
            <Clock className="size-7" />
          </span>
          <p className="mt-4 font-bold">Nothing here yet</p>
          <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-muted">
            Tap the tick or the cross on any meal idea. Every meal you liked or
            didn&apos;t will show up here, newest first.
          </p>
        </div>
      ) : (
        <ol className="mt-8 divide-y divide-subtle overflow-hidden rounded-3xl border border-subtle bg-surface">
          {ratings.ratings.map(({ meal, like, rated_at }) => (
            <li key={meal.recipe_id} className="flex items-center gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <button
                  type="button"
                  onClick={() => setOpen(meal)}
                  className="text-left font-bold leading-snug hover:text-accent"
                >
                  {meal.title}
                </button>
                <p className="mt-0.5 text-xs text-muted">{DATE.format(new Date(rated_at))}</p>
              </div>
              <span
                className={`inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${
                  like ? "bg-[#e8f2df] text-[#3f7a34]" : "bg-[#fdeee7] text-[#d4492a]"
                }`}
              >
                {like ? <Check className="size-3.5" /> : <Close className="size-3.5" />}
                {like ? "Liked" : "Not liked"}
              </span>
            </li>
          ))}
        </ol>
      )}

      <MealDialog
        meal={open}
        label="From your history"
        saved={open ? saved.isSaved(open.recipe_id) : false}
        saving={open !== null && saved.busy === open.recipe_id}
        error={open ? saved.error : null}
        onToggleSave={() => open && void saved.toggle(open)}
        onClose={() => setOpen(null)}
        rating={
          open && (
            <LikeButtons
              title={open.title}
              like={ratings.likeOf(open.recipe_id)}
              saving={ratings.busy === open.recipe_id}
              error={ratings.errors[open.recipe_id]}
              onRate={(like) => void ratings.rate(open, like)}
            />
          )
        }
      />
    </>
  );
}
