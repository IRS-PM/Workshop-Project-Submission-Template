import type { Metadata } from "next";
import AppShell from "@/components/app-shell";
import PreferencesForm from "@/components/preferences-form";

export const metadata: Metadata = {
  title: "Your preferences · Remymy",
  description: "Change your diet, cuisines and nutrient goal.",
};

export default function Page() {
  return (
    <AppShell>
      <p className="eyebrow">So we suggest the right things</p>
      <h1 className="mt-2 text-4xl font-extrabold tracking-tight">
        What do you eat?
      </h1>
      <p className="mt-3 max-w-md leading-relaxed text-muted">
        This shapes every idea Remymy suggests. Change it whenever you like.
      </p>

      <PreferencesForm />
    </AppShell>
  );
}
