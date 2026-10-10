"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { Card } from "@/components/ui/card";
import { getSupabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const { ready, session } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = (await getSupabase()?.auth.updateUser({ password })) ?? {};
    setBusy(false);
    if (error) setError(error.message);
    else router.push("/portfolio");
  }

  return (
    <div className="mx-auto max-w-md pt-6">
      <Card>
        <h1 className="text-lg font-semibold">Choose a new password</h1>
        {!ready ? null : !session ? (
          <p className="mt-2 text-muted">
            This reset link has expired or was already used. Request a new one from the sign-in
            page.
          </p>
        ) : (
          <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="label">New password</span>
              <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-base outline-none focus:border-accent"
              />
            </label>
            {error ? (
              <p role="alert" className="text-sm text-negative">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-accent px-3 py-2 font-medium text-accent-contrast disabled:opacity-60"
            >
              Save password
            </button>
          </form>
        )}
      </Card>
    </div>
  );
}
