import type { Metadata } from "next";
import { Suspense } from "react";
import { SignInForm } from "@/components/auth/sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-md pt-6">
      <Suspense>
        <SignInForm />
      </Suspense>
    </div>
  );
}
