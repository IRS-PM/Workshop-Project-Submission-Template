"use client";

import { useRouter } from "next/navigation";
import { useAccount } from "@/components/auth-gate";
import { logOut } from "@/lib/api";

export default function AccountBar() {
  const router = useRouter();
  const { username } = useAccount();

  async function signOut() {
    // Only the server can clear an HttpOnly cookie. If the call fails the
    // cookie survives, so send the user onward either way and let AuthGate
    // decide on the next load.
    try {
      await logOut();
    } finally {
      // replace, not push: Back must not return to a signed-in screen.
      router.replace("/signin");
    }
  }

  return (
    <div className="mb-7 flex items-center justify-end gap-3">
      <span className="text-sm text-muted">
        Signed in as <span className="font-bold text-foreground">{username}</span>
      </span>
      <button
        type="button"
        onClick={() => void signOut()}
        className="rounded-full border border-subtle px-4 py-2 text-sm font-semibold text-muted transition hover:border-sage-deep hover:text-foreground"
      >
        Log out
      </button>
    </div>
  );
}
