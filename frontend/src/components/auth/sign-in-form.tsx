"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { getSupabase } from "@/lib/supabase";
import { useAuth } from "./auth-provider";

type Mode = "sign-in" | "sign-up" | "reset";

const inputClass =
  "w-full rounded-lg border border-border bg-bg px-3 py-2 text-base outline-none focus:border-accent";

/** Only same-site paths, so a crafted link can't bounce users elsewhere. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/portfolio";
}

export function SignInForm() {
  const { configured, session, email: signedInAs, signOut } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!configured) {
    return (
      <Card>
        <h1 className="text-lg font-semibold">Sign-in is not configured</h1>
        <p className="mt-1 text-muted">
          This deployment has no Supabase project settings. Markets, Research and Risk Lab work
          without an account.
        </p>
      </Card>
    );
  }

  if (session) {
    return (
      <Card>
        <h1 className="text-lg font-semibold">You&apos;re signed in</h1>
        <p className="mt-1 text-muted">Signed in as {signedInAs}.</p>
        <div className="mt-4 flex gap-2">
          <Link
            href={next}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-contrast"
          >
            Continue
          </Link>
          <button
            type="button"
            onClick={() => signOut()}
            className="rounded-lg border border-border px-3 py-2 text-sm"
          >
            Sign out
          </button>
        </div>
      </Card>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const sb = getSupabase();
    if (!sb) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    const origin = window.location.origin;
    try {
      if (mode === "sign-in") {
        const { error } = await sb.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push(next);
      } else if (mode === "sign-up") {
        const { data, error } = await sb.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${origin}${next}` },
        });
        if (error) throw error;
        if (data.session) router.push(next);
        else setNotice("Check your email for a confirmation link, then sign in.");
      } else {
        const { error } = await sb.auth.resetPasswordForEmail(email, {
          redirectTo: `${origin}/account/reset`,
        });
        if (error) throw error;
        setNotice("If an account exists for that email, a reset link is on its way.");
      }
    } catch (err) {
      setError(friendly(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h1 className="text-lg font-semibold">
        {mode === "sign-up"
          ? "Create your account"
          : mode === "reset"
            ? "Reset password"
            : "Sign in"}
      </h1>
      <p className="mt-1 text-sm text-muted">
        An account keeps your portfolios, watchlists and alerts private to you.
      </p>
      {mode !== "reset" ? (
        <Segmented
          className="mt-4"
          label="Account action"
          options={[
            { value: "sign-in", label: "Sign in" },
            { value: "sign-up", label: "Create account" },
          ]}
          value={mode}
          onChange={(m) => {
            setMode(m);
            setError(null);
            setNotice(null);
          }}
        />
      ) : null}
      <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="label">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </label>
        {mode !== "reset" ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="label">Password</span>
            <input
              type="password"
              required
              minLength={8}
              autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
            {mode === "sign-up" ? (
              <span className="text-xs text-subtle">At least 8 characters.</span>
            ) : null}
          </label>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-negative">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="text-sm text-positive">
            {notice}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-accent px-3 py-2 font-medium text-accent-contrast disabled:opacity-60"
        >
          {busy
            ? "Please wait…"
            : mode === "sign-up"
              ? "Create account"
              : mode === "reset"
                ? "Send reset link"
                : "Sign in"}
        </button>
      </form>
      <div className="mt-3 text-sm">
        {mode === "reset" ? (
          <button type="button" className="text-muted underline" onClick={() => setMode("sign-in")}>
            Back to sign in
          </button>
        ) : (
          <button type="button" className="text-muted underline" onClick={() => setMode("reset")}>
            Forgot your password?
          </button>
        )}
      </div>
    </Card>
  );
}

function friendly(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (/invalid login credentials/i.test(msg)) return "That email and password don't match.";
  if (/email not confirmed/i.test(msg))
    return "Confirm your email first: open the link we sent you.";
  if (/rate limit/i.test(msg))
    return "Too many emails were sent recently. Please wait a while and try again.";
  if (/already registered/i.test(msg)) return "An account with this email already exists.";
  return msg || "Something went wrong. Please try again.";
}
