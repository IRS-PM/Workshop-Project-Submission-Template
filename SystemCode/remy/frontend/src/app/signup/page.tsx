import type { Metadata } from "next";
import Link from "next/link";
import AuthLayout from "@/components/auth-layout";
import RedirectIfSignedIn from "@/components/redirect-if-signed-in";
import SignUpForm from "@/components/signup-form";

export const metadata: Metadata = {
  title: "Create account · Remymy",
  description: "Create a Remymy account.",
};

export default function Page() {
  return (
    <AuthLayout
      title="Let's get you fed"
      subtitle="Make an account and we'll tune suggestions to how you actually eat."
      footer={
        <>
          Already cooking with us?{" "}
          <Link
            href="/signin"
            className="font-bold text-accent underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <RedirectIfSignedIn />
      <SignUpForm />
    </AuthLayout>
  );
}
