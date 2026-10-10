"use client";

import type { Session } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getSupabase } from "@/lib/supabase";

type AuthState = {
  /** False until the stored session has been read. */
  ready: boolean;
  configured: boolean;
  session: Session | null;
  email: string | null;
  /** A fresh access token (refreshed by the client when close to expiry). */
  getToken: () => Promise<string | null>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [configured, setConfigured] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    const sb = getSupabase();
    setConfigured(sb !== null);
    if (!sb) {
      setReady(true);
      return;
    }
    sb.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data } = sb.auth.onAuthStateChange((event, next) => {
      setSession(next);
      // Private data belongs to one user; drop it on sign-in/out.
      if (event === "SIGNED_OUT" || event === "SIGNED_IN") {
        queryClient.removeQueries({ queryKey: ["me"] });
      }
    });
    return () => data.subscription.unsubscribe();
  }, [queryClient]);

  const getToken = useCallback(async () => {
    const sb = getSupabase();
    if (!sb) return null;
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? null;
  }, []);

  const signOut = useCallback(async () => {
    await getSupabase()?.auth.signOut();
    queryClient.removeQueries({ queryKey: ["me"] });
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      configured,
      session,
      email: session?.user.email ?? null,
      getToken,
      signOut,
    }),
    [ready, configured, session, getToken, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
