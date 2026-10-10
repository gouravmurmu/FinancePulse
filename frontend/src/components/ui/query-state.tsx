"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { ApiError, ApiUnreachableError } from "@/lib/api";
import { ErrorState, SkeletonCard } from "./states";

/** Loading, waking-up and error states shared by every data panel. */
export function QueryState<T>({
  query,
  children,
  skeletonLines = 4,
  className,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => React.ReactNode;
  skeletonLines?: number;
  className?: string;
}) {
  if (query.data !== undefined) {
    return (
      <div
        className={className}
        style={{ opacity: query.isFetching ? 0.6 : 1, transition: "opacity 150ms" }}
      >
        {children(query.data)}
      </div>
    );
  }
  if (query.isError) {
    const err = query.error;
    const description =
      err instanceof ApiUnreachableError
        ? "The analytics server did not wake up in time. It runs on a free tier that sleeps when idle."
        : err instanceof ApiError
          ? err.message
          : "The response could not be read.";
    return <ErrorState description={description} onRetry={() => query.refetch()} />;
  }
  return (
    <div className={className}>
      <SkeletonCard lines={skeletonLines} />
      {query.failureCount > 0 ? (
        <p className="mt-2 text-sm text-muted" role="status">
          Waking the analytics server. Free-tier servers sleep when idle and can take up to a minute
          to start.
        </p>
      ) : null}
    </div>
  );
}
