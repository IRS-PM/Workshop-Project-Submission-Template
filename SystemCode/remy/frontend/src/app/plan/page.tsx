import type { Metadata } from "next";
import AppShell from "@/components/app-shell";
import PlanBuilder from "@/components/plan-builder";

export const metadata: Metadata = {
  title: "Meal plan · Remy",
  description: "Plan days of meals that fit your diet and nutrient goals.",
};

export default function Page() {
  return (
    <AppShell>
      <p className="eyebrow">Your week, sorted</p>
      <h1 className="mt-2 text-4xl font-extrabold tracking-tight">Meal plan</h1>
      <p className="mt-3 max-w-md leading-relaxed text-muted">
        Say how far ahead to plan and what to aim for. Remy picks recipes that
        hit your targets and keeps the days varied.
      </p>

      <PlanBuilder />
    </AppShell>
  );
}
