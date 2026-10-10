import Link from "next/link";
import { formatPercent } from "@/lib/format";
import { assetHref, type Quote } from "@/lib/market";

/** Tile colour intensity saturates at ±5% for daily moves, ±25% for longer periods. */
function tileStyle(change: number | null, cap: number): React.CSSProperties {
  if (change === null) return { background: "var(--surface-raised)" };
  const pct = Math.round(Math.min(Math.abs(change) / cap, 1) * 55);
  const pole = change >= 0 ? "var(--positive)" : "var(--negative)";
  return { background: `color-mix(in oklab, ${pole} ${pct}%, var(--surface-raised))` };
}

export function Heatmap({ quotes, period }: { quotes: Quote[]; period: string }) {
  const cap = period === "1D" || period === "1W" ? 0.05 : 0.25;
  const groups = new Map<string, Quote[]>();
  for (const q of quotes) {
    const key = q.sector ?? "Other";
    groups.set(key, [...(groups.get(key) ?? []), q]);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  return (
    <div className="flex flex-col gap-3">
      {sorted.map(([sector, qs]) => (
        <section key={sector}>
          <h3 className="label mb-1.5">{sector}</h3>
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(7.5rem,1fr))] gap-0.5">
            {qs.map((q) => (
              <li key={q.instrument_id}>
                <Link
                  href={assetHref(q.instrument_id)}
                  style={tileStyle(q.change_pct, cap)}
                  className="flex h-16 flex-col justify-between rounded-md px-2 py-1.5 hover:outline hover:outline-1 hover:outline-accent"
                  title={`${q.name}: ${q.change_pct !== null ? formatPercent(q.change_pct) : "no data"}`}
                >
                  <span className="truncate text-sm font-medium">{q.name}</span>
                  <span className="num text-sm">
                    {q.change_pct !== null ? (
                      <>
                        <span aria-hidden="true">
                          {q.change_pct > 0 ? "▲ " : q.change_pct < 0 ? "▼ " : ""}
                        </span>
                        {formatPercent(q.change_pct)}
                      </>
                    ) : (
                      "—"
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
