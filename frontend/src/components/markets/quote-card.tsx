import Link from "next/link";
import { Sparkline } from "@/components/charts/sparkline";
import { Card } from "@/components/ui/card";
import { Change } from "@/components/ui/change";
import { FreshnessChip } from "@/components/ui/freshness-chip";
import { formatPrice } from "@/lib/format";
import { assetHref, toChip, type Quote } from "@/lib/market";

export function QuoteCard({ q }: { q: Quote }) {
  return (
    <Card className="relative flex flex-col gap-2 transition-colors hover:border-accent/40">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={assetHref(q.instrument_id)}
          className="font-medium after:absolute after:inset-0"
        >
          {q.name}
        </Link>
        <FreshnessChip freshness={toChip(q.freshness)} className="shrink-0" />
      </div>
      <div className="flex items-end justify-between gap-2">
        <div>
          <div className="num text-lg font-semibold">
            {q.price !== null ? formatPrice(q.price, q.currency, q.asset_class) : "—"}
          </div>
          <Change value={q.change_pct} className="text-sm" />
          {q.converted ? <span className="ml-2 text-xs text-subtle">in {q.currency}</span> : null}
        </div>
        <Sparkline values={q.sparkline} />
      </div>
    </Card>
  );
}

export function MoverRow({ q }: { q: Quote }) {
  return (
    <li>
      <Link
        href={assetHref(q.instrument_id)}
        className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 hover:bg-surface-raised"
      >
        <span className="min-w-0 truncate">{q.name}</span>
        <span className="num shrink-0 text-muted">
          {q.price !== null ? formatPrice(q.price, q.currency, q.asset_class) : "—"}
        </span>
        <Change value={q.change_pct} className="w-20 shrink-0 text-right" />
      </Link>
    </li>
  );
}
