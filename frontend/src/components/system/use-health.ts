"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiUnreachableError, HealthSchema, apiGet } from "@/lib/api";

/**
 * Free-tier backends sleep when idle and take up to about a minute to boot.
 * Unreachable errors are retried with backoff for roughly 90 seconds so the UI
 * can show a "waking up" state instead of an error.
 */
export const WAKE_RETRIES = 6;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet("/api/v1/health", HealthSchema, { signal }),
    retry: (count, error) => error instanceof ApiUnreachableError && count < WAKE_RETRIES,
    retryDelay: (attempt) => Math.min(5_000 * 2 ** attempt, 20_000),
    refetchInterval: 5 * 60_000,
  });
}
