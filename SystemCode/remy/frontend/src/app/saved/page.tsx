import type { Metadata } from "next";
import AppShell from "@/components/app-shell";
import SavedMeals from "@/components/saved-meals";

export const metadata: Metadata = {
  title: "Saved meals · Remy",
  description: "The meals you kept for later.",
};

export default function Page() {
  return (
    <AppShell>
      <p className="eyebrow">Kept for later</p>
      <h1 className="mt-2 text-4xl font-extrabold tracking-tight">
        Saved meals
      </h1>

      <SavedMeals />
    </AppShell>
  );
}
