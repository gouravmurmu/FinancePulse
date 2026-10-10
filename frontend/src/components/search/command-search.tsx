"use client";

import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { ASSET_CLASS_LABEL, assetHref, marketApi } from "@/lib/market";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Global instrument search, opened with ⌘K / Ctrl+K or "/". */
export function CommandSearch() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const term = useDebounced(q.trim(), 150);

  const results = useQuery({
    queryKey: ["search", term],
    queryFn: () => marketApi.search(term, 10),
    enabled: open && term.length > 0,
    placeholderData: (prev) => prev,
  });
  const items = term ? (results.data ?? []) : [];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const typing =
        e.target instanceof HTMLElement && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  function go(id: string) {
    setOpen(false);
    setQ("");
    router.push(assetHref(id));
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 w-full max-w-sm items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm text-muted hover:border-accent/50"
      >
        <Search size={16} aria-hidden="true" />
        <span className="flex-1 text-left">Search stocks, indices, crypto…</span>
        <kbd className="hidden rounded border border-border px-1.5 text-xs sm:inline">⌘K</kbd>
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 px-4 pt-[12vh]"
          onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Search instruments"
            className="w-full max-w-lg overflow-hidden rounded-card border border-border bg-surface shadow-card"
          >
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search size={16} aria-hidden="true" className="text-muted" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setActive(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setOpen(false);
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive((a) => Math.min(a + 1, items.length - 1));
                  }
                  if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive((a) => Math.max(a - 1, 0));
                  }
                  if (e.key === "Enter" && items[active]) go(items[active].id);
                }}
                role="combobox"
                aria-expanded={items.length > 0}
                aria-controls={listId}
                aria-activedescendant={items[active] ? `${listId}-${active}` : undefined}
                placeholder="Apple, Nifty, BTC, gold…"
                className="h-12 flex-1 bg-transparent outline-none placeholder:text-subtle focus-visible:outline-none"
              />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close search"
                className="text-muted hover:text-text"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
            <ul id={listId} role="listbox" className="max-h-80 overflow-auto p-1">
              {items.map((it, i) => (
                <li
                  key={it.id}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(it.id)}
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2",
                    i === active && "bg-surface-raised",
                  )}
                >
                  <span className="min-w-0 truncate">{it.name}</span>
                  <span className="shrink-0 text-xs text-muted">
                    {ASSET_CLASS_LABEL[it.asset_class] ?? it.asset_class}
                    {it.exchange ? ` · ${it.exchange}` : ""}
                  </span>
                </li>
              ))}
              {term && results.isFetched && !items.length ? (
                <li className="px-3 py-6 text-center text-muted">No instruments match “{term}”.</li>
              ) : null}
              {!term ? (
                <li className="px-3 py-6 text-center text-sm text-muted">
                  Type a company, ticker, index, coin or metal.
                </li>
              ) : null}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  );
}
