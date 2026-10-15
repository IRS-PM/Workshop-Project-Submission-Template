"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Logo from "@/components/logo";
import { fetchAccount, refreshSession } from "@/lib/api";

const AccountContext = createContext<{ username: string }>({ username: "" });

/** The signed-in username, for anything rendered inside AuthGate. */
export const useAccount = () => useContext(AccountContext);

/**
 * Renders its children only once the backend has confirmed who the stored token
 * belongs to. Anyone without a usable token is sent to sign in.
 *
 * The frontend cannot inspect the session cookie, so asking the backend is the
 * only way to know whether one exists and who it belongs to. /me is the proof.
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        // Renew first, so a session that lapsed overnight comes back instead of
        // bouncing the user out. Both calls ride on the HttpOnly cookie.
        await refreshSession();
        const account = await fetchAccount();
        if (!cancelled) setUsername(account.username);
      } catch {
        // Either there is no cookie, or the backend rejected it. Nothing to
        // clean up locally - the token was never in this code's hands.
        if (!cancelled) router.replace("/signin");
      }
    }

    void check();
    return () => {
      cancelled = true;
    };
  }, [router]);

  // Held back deliberately: rendering the app first and redirecting after would
  // flash a signed-out user a screen they are not entitled to.
  if (username === null) {
    return (
      <div className="grid min-h-dvh place-items-center" aria-busy="true">
        <div className="animate-pulse">
          <Logo />
        </div>
      </div>
    );
  }

  return (
    <AccountContext.Provider value={{ username }}>
      {children}
    </AccountContext.Provider>
  );
}
