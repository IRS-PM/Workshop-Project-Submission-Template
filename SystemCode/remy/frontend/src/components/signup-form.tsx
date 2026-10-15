"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Field from "@/components/field";
import FormError from "@/components/form-error";
import { ApiError, checkUsername, signUp } from "@/lib/api";

const USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{2,31}$/;

export default function SignUpForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [username, setUsername] = useState("");
  const [checked, setChecked] = useState<{ username: string; available: boolean | null } | null>(null);

  const candidate = username.trim().toLowerCase();
  const wellFormed = USERNAME_PATTERN.test(candidate);
  const result = wellFormed && checked?.username === candidate ? checked.available : undefined;
  const taken = result === false;

  useEffect(() => {
    if (!wellFormed) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      checkUsername(candidate)
        .then(({ available }) => {
          if (!cancelled) setChecked({ username: candidate, available });
        })
        .catch(() => {
          if (!cancelled) setChecked({ username: candidate, available: null });
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [candidate, wellFormed]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setError(null);
    setPending(true);

    try {
      await signUp({
        username: String(data.get("username") ?? ""),
        password: String(data.get("password") ?? ""),
      });
      // A brand new account has no preference row yet, which is what the cold
      // start fills in.
      router.push("/welcome");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Something went wrong.",
      );
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field
        id="username"
        label="Username"
        autoComplete="username"
        placeholder="yourname"
        describedBy="username-status"
        onChange={setUsername}
      />
      <p
        id="username-status"
        aria-live="polite"
        className={`-mt-1 text-xs ${
          taken || (candidate.length >= 3 && !wellFormed)
            ? "font-semibold text-accent"
            : result === true
              ? "font-semibold text-sage-foreground"
              : "text-muted"
        }`}
      >
        {taken
          ? `“${candidate}” is already taken.`
          : result === true
            ? `“${candidate}” is available.`
            : wellFormed && result === undefined
              ? "Checking availability…"
              : "3–32 characters: letters, digits, dot, dash or underscore."}
      </p>

      <Field
        id="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        placeholder="At least 8 characters"
      />

      <FormError message={error} />

      <button
        type="submit"
        disabled={pending || taken}
        className="w-full rounded-full bg-accent px-4 py-3 text-sm font-bold text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? "Creating account…" : "Create account"}
      </button>

      <p className="text-center text-xs leading-relaxed text-muted">
        Next we&rsquo;ll ask three quick questions so your first suggestions
        actually fit.
      </p>
    </form>
  );
}
