import type { Metadata } from "next";
import AppShell from "@/components/app-shell";
import RatingHistory from "@/components/rating-history";

export const metadata: Metadata = {
  title: "History · Remy",
  description: "Every meal you liked or didn't, newest first.",
};

export default function Page() {
  return (
    <AppShell>
      <p className="eyebrow">What you&apos;ve rated</p>
      <h1 className="mt-2 text-4xl font-extrabold tracking-tight">History</h1>

      <RatingHistory />
    </AppShell>
  );
}
