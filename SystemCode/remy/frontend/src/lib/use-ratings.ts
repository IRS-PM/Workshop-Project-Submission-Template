"use client";

import { useEffect, useState } from "react";
import { ApiError, listRatings, rateMeal, type MealRating } from "@/lib/api";
import type { PlanMeal } from "@/lib/plan-api";

/** The signed-in user's likes, newest first, and a way to add one. Every page
 *  with like buttons uses this, so a meal shows the same like everywhere. */
export function useRatings() {
  // null while the first load is in flight.
  const [ratings, setRatings] = useState<MealRating[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    listRatings()
      .then((stored) => {
        if (!cancelled) setRatings(stored);
      })
      .catch((caught) => {
        if (cancelled) return;
        setRatings([]);
        setLoadError(caught instanceof ApiError ? caught.message : "Couldn't load your history.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  /** true liked, false not liked, undefined not rated yet. */
  const likeOf = (recipeId: string) => ratings?.find((rating) => rating.meal.recipe_id === recipeId)?.like;

  async function rate(meal: PlanMeal, like: boolean) {
    // The choice already saved is not sent again.
    if (busy || likeOf(meal.recipe_id) === like) return;
    setBusy(meal.recipe_id);
    setErrors((current) => {
      const next = { ...current };
      delete next[meal.recipe_id];
      return next;
    });

    try {
      const saved = await rateMeal(meal, like);
      setRatings((current) => [
        saved,
        ...(current ?? []).filter((rating) => rating.meal.recipe_id !== meal.recipe_id),
      ]);
    } catch (caught) {
      setErrors((current) => ({
        ...current,
        [meal.recipe_id]: caught instanceof ApiError ? caught.message : "Your rating could not be saved.",
      }));
    } finally {
      setBusy(null);
    }
  }

  return { ratings, loadError, likeOf, rate, busy, errors };
}
