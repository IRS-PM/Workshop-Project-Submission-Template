import type { Metadata } from "next";
import Link from "next/link";
import Logo from "@/components/logo";
import ColdStart from "@/components/cold-start";
import AuthGate from "@/components/auth-gate";

export const metadata: Metadata = {
  title: "Set up · Remymy",
  description: "Three quick questions so your first suggestions fit.",
};

export default function Page() {
  return (
    <AuthGate>
      <div className="flex min-h-dvh flex-col">
      <header className="px-6 py-6">
        <Link href="/">
          <Logo />
        </Link>
      </header>

      <main className="flex flex-1 items-start justify-center px-5 pb-16 sm:items-center sm:pb-20">
        <ColdStart />
      </main>
      </div>
    </AuthGate>
  );
}
