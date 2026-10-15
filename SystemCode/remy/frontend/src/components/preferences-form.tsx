"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Chip from "@/components/chip";
import FormError from "@/components/form-error";
import {
  CUISINES,
  DIETS,
  EMPTY_PREFERENCES,
  NUTRIENTS,
  type Diet,
  type Preferences,
} from "@/components/preference-options";
import { ApiError, loadPreferences, savePreferences } from "@/lib/api";

/** The in-app editor. Same options as the cold start, but all on one page:
 *  someone changing a setting does not want a wizard. */
export default function PreferencesForm() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<Preferences>(EMPTY_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load what is already stored before showing the form. Rendering empty
  // controls first would let a quick save overwrite real preferences with
  // blanks - the PUT replaces the whole set.
  useEffect(() => {
    let cancelled = false;

    loadPreferences()
      .then((stored) => {
        if (cancelled) return;
        if (stored) {
          setPrefs({
            diet: (stored.special_diet as Diet | null) ?? null,
            cuisines: stored.cuisines ?? [],
            nutrient: stored.preferred_nutrient ?? null,
          });
        }
      })
      .catch((caught) => {
        if (cancelled) return;
        if (caught instanceof ApiError && caught.status === 401) {
          router.push("/signin");
          return;
        }
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Could not load your preferences.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  function toggleCuisine(cuisine: string) {
    setPrefs((current) => ({
      ...current,
      cuisines: current.cuisines.includes(cuisine)
        ? current.cuisines.filter((item) => item !== cuisine)
        : [...current.cuisines, cuisine],
    }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSaving(true);

    try {
      await savePreferences({
        special_diet: prefs.diet,
        cuisines: prefs.cuisines,
        preferred_nutrient: prefs.nutrient,
      });
      router.push("/");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        router.push("/signin");
        return;
      }
      setError(
        caught instanceof ApiError ? caught.message : "Could not save that.",
      );
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mt-8 space-y-6" aria-busy="true">
        {[0, 1, 2].map((index) => (
          <div
            key={index}
            className="h-40 animate-pulse rounded-3xl border border-subtle bg-surface/60"
          />
        ))}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8 space-y-6">
      <fieldset className="rounded-3xl border border-subtle bg-surface p-6">
        <legend className="float-left w-full text-sm font-bold">Diet</legend>
        <p className="clear-both text-sm text-muted">Pick the one that fits you.</p>

        <div className="mt-4 grid gap-2.5 sm:grid-cols-3">
          {DIETS.map(({ id, label, hint }) => (
            <label
              key={id}
              className={`cursor-pointer rounded-2xl border p-4 transition ${
                prefs.diet === id
                  ? "border-accent bg-accent/5"
                  : "border-subtle hover:border-sage-deep"
              }`}
            >
              <input
                type="radio"
                name="diet"
                value={id}
                checked={prefs.diet === id}
                onChange={() =>
                  setPrefs((current) => ({ ...current, diet: id as Diet }))
                }
                className="sr-only"
              />
              <span className="block font-bold">{label}</span>
              <span className="mt-1 block text-sm leading-snug text-muted">
                {hint}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="rounded-3xl border border-subtle bg-surface p-6">
        <legend className="float-left w-full text-sm font-bold">Cuisines</legend>
        <p className="clear-both text-sm text-muted">
          Choose as many as you like, or skip and we&rsquo;ll suggest broadly.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {CUISINES.map((cuisine) => (
            <Chip
              key={cuisine}
              label={cuisine}
              selected={prefs.cuisines.includes(cuisine)}
              onClick={() => toggleCuisine(cuisine)}
            />
          ))}
        </div>
      </fieldset>

      <fieldset className="rounded-3xl border border-subtle bg-surface p-6">
        <legend className="float-left w-full text-sm font-bold">Aim for</legend>
        <p className="clear-both text-sm text-muted">
          One nutrient to steer suggestions by.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {NUTRIENTS.map((option) => (
            <Chip
              key={option}
              label={option}
              selected={prefs.nutrient === option}
              onClick={() =>
                setPrefs((current) => ({
                  ...current,
                  nutrient: current.nutrient === option ? null : option,
                }))
              }
            />
          ))}
        </div>
      </fieldset>

      <FormError message={error} />

      <button
        type="submit"
        disabled={prefs.diet === null || saving}
        className="rounded-full bg-accent px-6 py-3 text-sm font-bold text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {saving ? "Saving…" : "Save preferences"}
      </button>
    </form>
  );
}
