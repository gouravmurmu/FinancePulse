"use client";

import Link from "next/link";
import { Check, Eye, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { errorMessage } from "@/components/portfolio/forms";
import { useWatchlistMutations, useWatchlists } from "@/lib/portfolio";

/** Add or remove the current asset from the user's watchlists. */
export function WatchButton({ instrumentId }: { instrumentId: string }) {
  const { ready, configured, session } = useAuth();
  const lists = useWatchlists();
  const m = useWatchlistMutations();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)
      )
        setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (!ready || !configured) return null;
  if (!session) {
    return (
      <Link
        href={`/sign-in?next=${encodeURIComponent(`/assets/${encodeURIComponent(instrumentId)}`)}`}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-sm text-muted hover:text-text"
      >
        <Eye size={15} aria-hidden="true" /> Watch
      </Link>
    );
  }
  const watching = (lists.data ?? []).filter((w) => w.instrument_ids.includes(instrumentId));
  const busy = m.addItem.isPending || m.removeItem.isPending || m.create.isPending;
  const error = m.addItem.error ?? m.removeItem.error ?? m.create.error;

  async function quickAdd() {
    // First watch: create a default list and add to it in one click.
    const created = await m.create.mutateAsync("Watchlist");
    m.addItem.mutate({ id: created.id, instrumentId });
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
        onClick={() => (lists.data?.length ? setOpen((o) => !o) : void quickAdd())}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-sm hover:border-accent disabled:opacity-60"
      >
        {watching.length ? (
          <Check size={15} aria-hidden="true" className="text-accent" />
        ) : (
          <Eye size={15} aria-hidden="true" />
        )}
        {watching.length ? "Watching" : "Watch"}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-40 w-64 rounded-card border border-border bg-surface-raised p-2 shadow-card"
        >
          {(lists.data ?? []).map((w) => {
            const on = w.instrument_ids.includes(instrumentId);
            return (
              <button
                key={w.id}
                type="button"
                role="menuitemcheckbox"
                aria-checked={on}
                disabled={busy}
                onClick={() =>
                  on
                    ? m.removeItem.mutate({ id: w.id, instrumentId })
                    : m.addItem.mutate({ id: w.id, instrumentId })
                }
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface"
              >
                <span className="inline-flex size-4 items-center justify-center rounded border border-border">
                  {on ? <Check size={12} aria-hidden="true" /> : null}
                </span>
                <span className="truncate">{w.name}</span>
                <span className="ml-auto text-xs text-subtle">{w.instrument_ids.length}</span>
              </button>
            );
          })}
          <form
            className="mt-1 flex gap-1 border-t border-border pt-2"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!name.trim()) return;
              const created = await m.create.mutateAsync(name.trim());
              m.addItem.mutate({ id: created.id, instrumentId });
              setName("");
            }}
          >
            <input
              aria-label="New watchlist name"
              placeholder="New list"
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1 text-sm"
            />
            <button
              type="submit"
              aria-label="Create list and add"
              className="rounded-md border border-border px-2 text-muted hover:text-text"
            >
              <Plus size={15} aria-hidden="true" />
            </button>
          </form>
          {error ? <p className="mt-1 px-1 text-xs text-negative">{errorMessage(error)}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
