"use client";

import { useEffect, useState } from "react";
import { ApiError, listSavedMeals, removeSavedMeal, saveMeals } from "@/lib/api";
import type { PlanMeal } from "@/lib/plan-api";

/** The signed-in user's saved meals, plus a bookmark-style toggle. Shared by
 *  the home page ideas and the Saved page so both agree on what is saved. */
export function useSavedMeals() {
  // null while the first load is in flight.
  const [meals, setMeals] = useState<PlanMeal[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSavedMeals()
      .then((saved) => {
        if (!cancelled) setMeals(saved);
      })
      .catch((caught) => {
        if (cancelled) return;
        setMeals([]);
        setError(caught instanceof ApiError ? caught.message : "Couldn't load your saved meals.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isSaved = (recipeId: string) => meals?.some((meal) => meal.recipe_id === recipeId) ?? false;

  async function toggle(meal: PlanMeal) {
    if (busy) return;
    setBusy(meal.recipe_id);
    setError(null);

    try {
      if (isSaved(meal.recipe_id)) {
        try {
          await removeSavedMeal(meal.recipe_id);
        } catch (caught) {
          // Already gone on the server, which is what we wanted anyway.
          if (!(caught instanceof ApiError && caught.status === 404)) throw caught;
        }
        setMeals((current) => current?.filter((saved) => saved.recipe_id !== meal.recipe_id) ?? null);
      } else {
        setMeals(await saveMeals([meal]));
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't update your saved meals.");
    } finally {
      setBusy(null);
    }
  }

  return { meals, isSaved, toggle, busy, error };
}
