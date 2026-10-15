"use client";

import { useState } from "react";
import { Heart } from "@/components/icons";
import LikeButtons from "@/components/like-buttons";
import MealDialog from "@/components/meal-dialog";
import { MealCard } from "@/components/plan-view";
import type { PlanMeal } from "@/lib/plan-api";
import { useRatings } from "@/lib/use-ratings";
import { useSavedMeals } from "@/lib/use-saved-meals";

export default function SavedMeals() {
  const saved = useSavedMeals();
  // Held apart from the list, so un-bookmarking in the pop-up keeps it open
  // and the meal can be saved again straight away.
  const [open, setOpen] = useState<PlanMeal | null>(null);
  const ratings = useRatings();

  const likeButtons = (meal: PlanMeal) => (
    <LikeButtons
      title={meal.title}
      like={ratings.likeOf(meal.recipe_id)}
      saving={ratings.busy === meal.recipe_id}
      error={ratings.errors[meal.recipe_id]}
      onRate={(like) => void ratings.rate(meal, like)}
    />
  );

  if (saved.meals === null) {
    return <p className="mt-8 animate-pulse text-sm text-muted">Loading your saved meals…</p>;
  }

  return (
    <>
      {saved.error && !open && <p className="mt-6 text-sm text-accent">{saved.error}</p>}

      {saved.meals.length === 0 ? (
        <div className="mt-8 rounded-3xl border border-dashed border-subtle bg-surface/60 px-6 py-16 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-cream text-muted">
            <Heart className="size-7" />
          </span>
          <p className="mt-4 font-bold">Nothing saved yet</p>
          <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-muted">
            Open any idea on the home page and tap the bookmark. It will wait for
            you here, ready for the next time you cannot decide.
          </p>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {saved.meals.map((meal) => (
            <MealCard
              key={meal.recipe_id}
              meal={meal}
              label="Saved"
              saved
              onOpen={() => setOpen(meal)}
              footer={likeButtons(meal)}
            />
          ))}
        </ul>
      )}

      <MealDialog
        meal={open}
        label="Saved meal"
        saved={open ? saved.isSaved(open.recipe_id) : false}
        saving={open !== null && saved.busy === open.recipe_id}
        error={open ? saved.error : null}
        onToggleSave={() => open && void saved.toggle(open)}
        onClose={() => setOpen(null)}
        rating={open && likeButtons(open)}
      />
    </>
  );
}
