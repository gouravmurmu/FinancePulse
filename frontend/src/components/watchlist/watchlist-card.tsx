"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { MoverRow } from "@/components/markets/quote-card";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { useWatchlist, useWatchlists } from "@/lib/portfolio";

/** Signed-in users see their watchlist on the Markets page; others see nothing. */
export function WatchlistCard({ currency }: { currency: "USD" | "INR" }) {
  const { session } = useAuth();
  const lists = useWatchlists();
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    if (!id && lists.data?.length) setId(lists.data[0].id);
  }, [id, lists.data]);
  const wl = useWatchlist(id, currency);
  if (!session || !lists.data) return null;
  if (!lists.data.length) {
    return (
      <Card>
        <CardHeader title="Watchlist" />
        <p className="text-sm text-muted">
          Open any asset and choose <span className="font-medium text-text">Watch</span> to follow
          it here.
        </p>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader
        title="Watchlist"
        subtitle="Change since the previous close"
        action={
          lists.data.length > 1 ? (
            <select
              aria-label="Choose watchlist"
              value={id ?? ""}
              onChange={(e) => setId(e.target.value)}
              className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
            >
              {lists.data.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          ) : undefined
        }
      />
      <QueryState query={wl} skeletonLines={3}>
        {(w) =>
          w.quotes?.length ? (
            <ul>
              {w.quotes.map((q) => (
                <MoverRow key={q.instrument_id} q={q} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">
              This watchlist is empty. Add assets from their pages, or{" "}
              <Link href="/research" className="underline">
                browse Research
              </Link>
              .
            </p>
          )
        }
      </QueryState>
    </Card>
  );
}
