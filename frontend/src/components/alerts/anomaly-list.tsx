"use client";

import Link from "next/link";
import { useInstrumentIndex, type Anomaly } from "@/lib/alerts";
import { formatDate } from "@/lib/format";
import { assetHref } from "@/lib/market";

const KIND_STYLE: Record<Anomaly["kind"], string> = {
  return: "border-accent/40 text-accent",
  volume: "border-border text-muted",
  volatility: "border-negative/40 text-negative",
  correlation: "border-border text-muted",
};

/** Statistical flags, newest first. Labels describe what happened, never what to do. */
export function AnomalyList({
  items,
  showInstrument = false,
  empty,
}: {
  items: Anomaly[];
  showInstrument?: boolean;
  empty: string;
}) {
  const index = useInstrumentIndex();
  if (items.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="flex flex-col divide-y divide-border">
      {items.map((a) => (
        <li key={`${a.instrument_id}-${a.observed_at}-${a.kind}`} className="py-2.5">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className={`rounded-full border px-2 py-0.5 text-xs ${KIND_STYLE[a.kind]}`}>
              {a.label}
            </span>
            {showInstrument ? (
              <Link href={assetHref(a.instrument_id)} className="font-medium hover:underline">
                {index.data?.[a.instrument_id]?.name ?? a.instrument_id}
              </Link>
            ) : null}
            <span className="text-xs text-subtle">{formatDate(a.observed_at)}</span>
          </div>
          <p className="mt-1 text-sm text-muted">{a.description}</p>
        </li>
      ))}
    </ul>
  );
}
