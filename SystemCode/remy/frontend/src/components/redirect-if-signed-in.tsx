"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchAccount } from "@/lib/api";

/**
 * Sends an already signed-in visitor straight to the homepage.
 *
 * Asks the backend whether the cookie names anyone. A 401 means no session and
 * the sign in form stays put.
 */
export default function RedirectIfSignedIn() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;

    // The session cookie is HttpOnly, so its presence can only be discovered by
    // asking. A 401 simply means "not signed in" - stay on this page.
    fetchAccount()
      .then(() => {
        if (!cancelled) router.replace("/");
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [router]);

  return null;
}
