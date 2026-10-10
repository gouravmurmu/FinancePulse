"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { ASSET_CLASS_LABEL, assetHref, marketApi, type Instrument } from "@/lib/market";

const GROUPS: { key: string; title: string; match: (i: Instrument) => boolean }[] = [
  { key: "index", title: "Indices", match: (i) => i.asset_class === "index" },
  { key: "us", title: "US stocks", match: (i) => i.asset_class === "equity" && i.country === "US" },
  {
    key: "in",
    title: "Indian stocks",
    match: (i) => i.asset_class === "equity" && i.country === "IN",
  },
  { key: "crypto", title: "Crypto", match: (i) => i.asset_class === "crypto" },
  {
    key: "metals",
    title: "Gold and silver",
    match: (i) => i.asset_class === "commodity" || i.asset_class === "etf",
  },
  { key: "fx", title: "Currency", match: (i) => i.asset_class === "fx" },
];

export function ResearchBrowser() {
  const [filter, setFilter] = useState("all");
  const [text, setText] = useState("");
  const query = useQuery({
    queryKey: ["instruments"],
    queryFn: marketApi.instruments,
    staleTime: 3_600_000,
  });

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">Research</h1>
        <p className="mt-1 max-w-prose text-muted">
          Open any instrument for its chart, indicators, risk profile and context. Press ⌘K anywhere
          to jump straight to one.
        </p>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Filter by name"
          aria-label="Filter instruments by name"
          className="h-9 w-56 rounded-lg border border-border bg-surface px-3 text-sm placeholder:text-subtle"
        />
        <Segmented
          label="Asset type"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "All" },
            ...GROUPS.map((g) => ({ value: g.key, label: g.title })),
          ]}
        />
      </div>
      <QueryState query={query} skeletonLines={8}>
        {(all) => <Groups all={all} filter={filter} text={text} />}
      </QueryState>
    </div>
  );
}

function Groups({ all, filter, text }: { all: Instrument[]; filter: string; text: string }) {
  const t = text.trim().toLowerCase();
  const groups = useMemo(
    () =>
      GROUPS.filter((g) => filter === "all" || g.key === filter)
        .map((g) => ({
          ...g,
          items: all.filter(
            (i) =>
              g.match(i) &&
              (!t || i.name.toLowerCase().includes(t) || i.id.toLowerCase().includes(t)),
          ),
        }))
        .filter((g) => g.items.length),
    [all, filter, t],
  );
  if (!groups.length) return <p className="text-muted">No instruments match “{text}”.</p>;
  return (
    <div className="flex flex-col gap-6">
      {groups.map((g) => (
        <section key={g.key} aria-labelledby={`g-${g.key}`}>
          <h2 id={`g-${g.key}`} className="label mb-2">
            {g.title}
          </h2>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {g.items.map((i) => (
              <Card key={i.id} className="relative py-3 transition-colors hover:border-accent/40">
                <Link href={assetHref(i.id)} className="font-medium after:absolute after:inset-0">
                  {i.name}
                </Link>
                <p className="text-xs text-muted">
                  {[
                    ASSET_CLASS_LABEL[i.asset_class] ?? i.asset_class,
                    i.exchange,
                    i.sector,
                    i.currency,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
