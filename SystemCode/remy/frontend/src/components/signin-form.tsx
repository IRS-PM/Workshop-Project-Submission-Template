"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Field from "@/components/field";
import FormError from "@/components/form-error";
import { ApiError, signIn, signInDemo } from "@/lib/api";

export default function SignInForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<"form" | "demo" | null>(null);

  async function run(kind: "form" | "demo", attempt: () => Promise<unknown>) {
    setError(null);
    setPending(kind);

    try {
      await attempt();
      // Returning users already have a preference row, so no cold start.
      router.push("/");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Something went wrong.",
      );
      // Only on failure: on success the route change unmounts this form, and
      // clearing pending first would flash the button back to its idle label.
      setPending(null);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    run("form", () =>
      signIn({
        username: String(data.get("username") ?? ""),
        password: String(data.get("password") ?? ""),
      }),
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field
        id="username"
        label="Username"
        autoComplete="username"
        placeholder="yourname"
      />
      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        placeholder="••••••••"
      />

      <FormError message={error} />

      <button
        type="submit"
        disabled={pending !== null}
        className="w-full rounded-full bg-accent px-4 py-3 text-sm font-bold text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending === "form" ? "Signing in…" : "Sign in"}
      </button>

      <button
        type="button"
        onClick={() => run("demo", signInDemo)}
        disabled={pending !== null}
        className="w-full rounded-full border border-accent px-4 py-3 text-sm font-bold text-accent transition hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending === "demo" ? "Opening demo…" : "Try the demo"}
      </button>
    </form>
  );
}
