"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useId, useState } from "react";
import { cn } from "@/lib/cn";
import { ASSET_CLASS_LABEL, marketApi, type Instrument } from "@/lib/market";
import { MAX_SERIES, seriesColor } from "@/lib/series";

/** Selected instruments as coloured chips plus an inline search to add more. */
export function InstrumentPicker({
  selected,
  slots,
  names,
  onAdd,
  onRemove,
  max = MAX_SERIES,
}: {
  selected: string[];
  slots: Record<string, number>;
  names: Record<string, string>;
  onAdd: (i: Instrument) => void;
  onRemove: (id: string) => void;
  max?: number;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const term = q.trim();
  const results = useQuery({
    queryKey: ["search", term],
    queryFn: () => marketApi.search(term, 8),
    enabled: term.length > 0,
  });
  const items = (results.data ?? []).filter((i) => !selected.includes(i.id));
  const full = selected.length >= max;

  function add(i: Instrument) {
    onAdd(i);
    setQ("");
    setActive(0);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {selected.map((id) => (
        <span
          key={id}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-raised py-1 pl-2.5 pr-1 text-sm"
        >
          <span
            aria-hidden="true"
            className="size-2 rounded-full"
            style={{ background: seriesColor(slots[id] ?? 0) }}
          />
          {names[id] ?? id}
          <button
            type="button"
            onClick={() => onRemove(id)}
            aria-label={`Remove ${names[id] ?? id}`}
            className="rounded-full p-0.5 text-muted hover:bg-surface hover:text-text"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </span>
      ))}
      {full ? (
        <span className="text-xs text-subtle">Up to {max} instruments.</span>
      ) : (
        <div className="relative">
          <div className="flex items-center gap-1 rounded-full border border-dashed border-border px-2.5 py-1 text-sm focus-within:border-accent">
            <Plus size={14} aria-hidden="true" className="text-muted" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOpen(true);
                setActive(0);
              }}
              onFocus={() => setOpen(true)}
              onBlur={() => setTimeout(() => setOpen(false), 150)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActive((a) => Math.min(a + 1, items.length - 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActive((a) => Math.max(a - 1, 0));
                } else if (e.key === "Enter" && items[active]) {
                  e.preventDefault();
                  add(items[active]);
                } else if (e.key === "Escape") setOpen(false);
              }}
              role="combobox"
              aria-label="Add instrument"
              aria-expanded={open && items.length > 0}
              aria-controls={listId}
              aria-activedescendant={items[active] ? `${listId}-${active}` : undefined}
              placeholder="Add instrument"
              className="w-36 bg-transparent outline-none placeholder:text-subtle focus-visible:outline-none"
            />
          </div>
          {open && items.length ? (
            <ul
              id={listId}
              role="listbox"
              className="absolute left-0 top-full z-30 mt-1 w-72 rounded-lg border border-border bg-surface p-1 shadow-card"
            >
              {items.map((it, i) => (
                <li
                  key={it.id}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    add(it);
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={cn(
                    "flex cursor-pointer justify-between gap-2 rounded-md px-2 py-1.5 text-sm",
                    i === active && "bg-surface-raised",
                  )}
                >
                  <span className="truncate">{it.name}</span>
                  <span className="shrink-0 text-xs text-muted">
                    {ASSET_CLASS_LABEL[it.asset_class] ?? it.asset_class}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  );
}
