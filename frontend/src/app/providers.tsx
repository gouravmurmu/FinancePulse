"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { WAKE_RETRIES } from "@/components/system/use-health";
import { AuthProvider } from "@/components/auth/auth-provider";
import { ApiUnreachableError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            // Keep retrying while a sleeping free-tier API boots; fail fast otherwise.
            retry: (count, error) => error instanceof ApiUnreachableError && count < WAKE_RETRIES,
            retryDelay: (attempt) => Math.min(5_000 * 2 ** attempt, 20_000),
          },
        },
      }),
  );
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem themes={["dark", "light"]}>
      <QueryClientProvider client={client}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
