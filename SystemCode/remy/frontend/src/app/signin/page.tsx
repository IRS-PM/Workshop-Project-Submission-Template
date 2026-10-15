import type { Metadata } from "next";
import Link from "next/link";
import AuthLayout from "@/components/auth-layout";
import RedirectIfSignedIn from "@/components/redirect-if-signed-in";
import SignInForm from "@/components/signin-form";

export const metadata: Metadata = {
  title: "Sign in · Remymy",
  description: "Sign in to Remymy.",
};

export default function Page() {
  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Pick up where you left off — your preferences are already saved."
      footer={
        <>
          New here?{" "}
          <Link
            href="/signup"
            className="font-bold text-accent underline-offset-4 hover:underline"
          >
            Create an account
          </Link>
        </>
      }
    >
      <RedirectIfSignedIn />
      <SignInForm />
    </AuthLayout>
  );
}
