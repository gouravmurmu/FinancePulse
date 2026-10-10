"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, Info } from "lucide-react";
import { useMemo, useState } from "react";
import { Donut } from "@/components/charts/donut";
import { Card, CardHeader } from "@/components/ui/card";
import { Change } from "@/components/ui/change";
import { FreshnessChip } from "@/components/ui/freshness-chip";
import { MetricCard } from "@/components/ui/metric-card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { EmptyState } from "@/components/ui/states";
import { abbreviate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { toChip } from "@/lib/market";
import { useSummary, type Holding, type Portfolio, type Summary } from "@/lib/portfolio";
import { primaryClass } from "./forms";

type Dim = "holding" | "asset_class" | "currency" | "sector";

export function Overview({ portfolio, onAdd }: { portfolio: Portfolio; onAdd: () => void }) {
  const summary = useSummary(portfolio.id);
  return (
    <QueryState query={summary} skeletonLines={8}>
      {(s) =>
        s.holdings.length === 0 && s.closed.length === 0 ? (
          <EmptyState
            title="No transactions yet"
            description="Add your first buy, or import a CSV, to see holdings, profit and loss and allocation."
            action={
              <button type="button" className={primaryClass} onClick={onAdd}>
                Add a transaction
              </button>
            }
          />
        ) : (
          <OverviewBody s={s} />
        )
      }
    </QueryState>
  );
}

function pnlTone(v: number | null | undefined) {
  return v == null || v === 0 ? "default" : v > 0 ? "positive" : "negative";
}

function signedMoney(v: number | null | undefined, ccy: "USD" | "INR") {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${formatMoney(v, ccy)}`;
}

function OverviewBody({ s }: { s: Summary }) {
  const ccy = s.base_currency;
  const t = s.totals;
  const [dim, setDim] = useState<Dim>("asset_class");
  const slices = s.allocation[dim]
    .filter((x) => x.value != null && x.weight != null)
    .map((x) => ({ label: x.label, value: x.value!, weight: x.weight! }));
  const top = s.holdings[0];
  const stale = s.holdings.filter(
    (h) => h.freshness.kind === "stale" || h.freshness.kind === "unavailable",
  );

  return (
    <div className="flex flex-col gap-6">
      {t ? (
        <>
          <p className="text-md">{insight(s)}</p>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard
              label="Market value"
              value={formatMoney(t.value ?? 0, ccy)}
              hint={`Cost ${formatMoney(t.cost ?? 0, ccy)}`}
              freshness={s.as_of ? { kind: "eod", asOf: s.as_of } : undefined}
            />
            <MetricCard
              label="Unrealized P&L"
              value={signedMoney(t.unrealized, ccy)}
              tone={pnlTone(t.unrealized)}
              hint={<Change value={t.unrealized_pct} />}
            />
            <MetricCard
              label="Realized P&L"
              value={signedMoney(t.realized, ccy)}
              tone={pnlTone(t.realized)}
              hint={`Fees paid ${formatMoney(t.fees ?? 0, ccy)}`}
            />
            <MetricCard
              label="Currency effect"
              value={signedMoney(t.fx_effect, ccy)}
              tone={pnlTone(t.fx_effect)}
              hint="Part of unrealized P&L from USD/INR moves"
            />
          </div>
        </>
      ) : null}

      {stale.length ? (
        <p
          className="rounded-lg border border-warning/40 px-3 py-2 text-sm text-warning"
          role="status"
        >
          Prices for {stale.map((h) => h.name).join(", ")} are stale or missing, so their value may
          be out of date.
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_380px] [&>*]:min-w-0">
        <Card>
          <CardHeader
            title="Holdings"
            subtitle={`${s.holdings.length} open positions, valued in ${ccy}${top ? `; largest is ${top.name}` : ""}`}
          />
          <HoldingsTable holdings={s.holdings} ccy={ccy} />
        </Card>
        <Card>
          <CardHeader title="Allocation" subtitle="Share of market value" />
          <Segmented
            className="mb-4"
            label="Group allocation by"
            options={[
              { value: "asset_class", label: "Asset class" },
              { value: "holding", label: "Holding" },
              { value: "sector", label: "Sector" },
              { value: "currency", label: "Currency" },
            ]}
            value={dim}
            onChange={setDim}
          />
          {slices.length ? (
            <Donut
              slices={slices}
              format={(v) => abbreviate(v, ccy)}
              caption={`Allocation by ${dim.replace("_", " ")}`}
            />
          ) : (
            <p className="text-muted">No priced holdings to allocate.</p>
          )}
        </Card>
      </div>

      {s.closed.length ? (
        <Card>
          <CardHeader
            title="Closed positions"
            subtitle="Fully sold; realized P&L in base currency"
          />
          <ul className="divide-y divide-border text-sm">
            {s.closed.map((c) => (
              <li key={c.instrument_id} className="flex justify-between py-2">
                <Link
                  href={`/assets/${encodeURIComponent(c.instrument_id)}`}
                  className="hover:underline"
                >
                  {c.name}
                </Link>
                <span className={`num font-medium ${pnlClass(c.realized_base)}`}>
                  {signedMoney(c.realized_base, ccy)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <ul className="flex flex-col gap-1 text-xs text-subtle">
        {s.notes.map((n) => (
          <li key={n} className="flex gap-1.5">
            <Info size={12} aria-hidden="true" className="mt-0.5 shrink-0" />
            {n}
          </li>
        ))}
      </ul>
    </div>
  );
}

function pnlClass(v: number | null | undefined) {
  return v == null || v === 0 ? "" : v > 0 ? "text-positive" : "text-negative";
}

function insight(s: Summary): string {
  const t = s.totals!;
  const ccy = s.base_currency;
  if (t.value == null) return "Your holdings have no prices yet.";
  const parts = [`Your portfolio is worth ${formatMoney(t.value, ccy)}`];
  if (t.unrealized != null && t.unrealized_pct != null) {
    parts.push(
      `${t.unrealized >= 0 ? "up" : "down"} ${formatPercent(Math.abs(t.unrealized_pct), { signed: false })} on what you paid`,
    );
  }
  const big = s.holdings[0];
  let text = parts.join(", ") + ".";
  if (big?.weight != null && big.weight > 0.4 && s.holdings.length > 1) {
    text += ` ${big.name} is ${formatPercent(big.weight, { signed: false })} of it, so it drives most of the swings.`;
  }
  return text;
}

type SortKey = "name" | "value_base" | "unrealized_base" | "unrealized_pct" | "weight";

function HoldingsTable({ holdings, ccy }: { holdings: Holding[]; ccy: "USD" | "INR" }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "value_base", dir: -1 });
  const rows = useMemo(() => {
    const out = [...holdings];
    out.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv) * sort.dir;
      return ((Number(av ?? -Infinity) || 0) - (Number(bv ?? -Infinity) || 0)) * sort.dir;
    });
    return out;
  }, [holdings, sort]);

  const head = (key: SortKey, label: string, right = true) => {
    const active = sort.key === key;
    return (
      <th
        scope="col"
        aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
        className={`px-3 py-2 font-medium text-muted ${right ? "text-right" : "text-left"}`}
      >
        <button
          type="button"
          className="inline-flex items-center gap-1 hover:text-text"
          onClick={() => setSort({ key, dir: active ? (sort.dir === 1 ? -1 : 1) : -1 })}
        >
          {label}
          {active ? (
            sort.dir === 1 ? (
              <ArrowUp size={12} aria-hidden="true" />
            ) : (
              <ArrowDown size={12} aria-hidden="true" />
            )
          ) : null}
        </button>
      </th>
    );
  };

  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="num w-full min-w-[720px] text-sm">
        <caption className="sr-only">Open positions</caption>
        <thead className="sticky top-0 bg-surface">
          <tr className="border-b border-border">
            {head("name", "Holding", false)}
            <th scope="col" className="px-3 py-2 text-right font-medium text-muted">
              Quantity
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium text-muted">
              Avg cost / Price
            </th>
            {head("value_base", `Value (${ccy})`)}
            {head("unrealized_base", "Unrealized")}
            {head("unrealized_pct", "Return")}
            {head("weight", "Weight")}
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr
              key={h.instrument_id}
              className="border-b border-border odd:bg-text/[0.02] hover:bg-surface-raised"
            >
              <th scope="row" className="sticky left-0 bg-surface px-3 py-2 text-left font-normal">
                <Link
                  href={`/assets/${encodeURIComponent(h.instrument_id)}`}
                  className="font-medium hover:underline"
                >
                  {h.name}
                </Link>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-subtle">
                  {h.asset_class_label}
                  {h.freshness.kind === "stale" || h.freshness.kind === "unavailable" ? (
                    <FreshnessChip freshness={toChip(h.freshness)} />
                  ) : null}
                </div>
              </th>
              <td className="px-3 py-2 text-right">
                {formatNumber(h.quantity, h.quantity < 1 ? 6 : 2)}
                {h.unit !== "unit" ? (
                  <span className="text-subtle"> {h.unit === "gram" ? "g" : "oz t"}</span>
                ) : null}
              </td>
              <td className="px-3 py-2 text-right">
                <div>{h.average_cost != null ? formatMoney(h.average_cost, h.currency) : "—"}</div>
                <div className="text-xs text-muted">
                  {h.price != null ? formatMoney(h.price, h.currency) : "No price"}
                </div>
              </td>
              <td className="px-3 py-2 text-right font-medium">
                {h.value_base != null ? formatMoney(h.value_base, ccy) : "—"}
              </td>
              <td className={`px-3 py-2 text-right ${pnlClass(h.unrealized_base)}`}>
                {signedMoney(h.unrealized_base, ccy)}
                {h.fx_effect_base ? (
                  <div className="text-xs text-muted" title="Part of this from USD/INR moves">
                    FX {signedMoney(h.fx_effect_base, ccy)}
                  </div>
                ) : null}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right">
                <Change value={h.unrealized_pct} />
              </td>
              <td className="px-3 py-2 text-right">
                {h.weight != null ? formatPercent(h.weight, { signed: false }) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
