"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Clock } from "lucide-react";
import { useMemo, useState } from "react";
import { LineChart } from "@/components/charts/line-chart";
import { Card, CardHeader } from "@/components/ui/card";
import { WatchlistCard } from "@/components/watchlist/watchlist-card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { EmptyState } from "@/components/ui/states";
import { formatDate, formatNumber } from "@/lib/format";
import {
  PERIODS,
  marketApi,
  type DisplayCurrency,
  type Overview,
  type Period,
  type Region,
} from "@/lib/market";
import { seriesColor } from "@/lib/series";
import { Heatmap } from "./heatmap";
import { MoverRow, QuoteCard } from "./quote-card";

const PERIOD_LABEL: Record<Period, string> = {
  "1D": "today",
  "1W": "1 week",
  "1M": "1 month",
  "3M": "3 months",
  "6M": "6 months",
  YTD: "year to date",
  "1Y": "1 year",
  "3Y": "3 years",
  "5Y": "5 years",
  MAX: "all history",
};

export function MarketsDashboard() {
  const [region, setRegion] = useState<Region>("global");
  const [currency, setCurrency] = useState<DisplayCurrency>("USD");
  const [period, setPeriod] = useState<Period>("1D");
  const query = useQuery({
    queryKey: ["overview", region, currency, period],
    queryFn: () => marketApi.overview(region, currency, period),
    placeholderData: (prev) => prev,
  });

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Markets</h1>
          <p className="mt-1 max-w-prose text-muted">
            Indices, stocks, crypto, gold and silver. Change is over {PERIOD_LABEL[period]}.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Segmented
            label="Region"
            value={region}
            onChange={setRegion}
            options={[
              { value: "global", label: "Global" },
              { value: "india", label: "India" },
            ]}
          />
          <Segmented
            label="Currency"
            value={currency}
            onChange={setCurrency}
            options={["USD", "INR"] as const}
          />
          <Segmented
            label="Period"
            value={period}
            onChange={setPeriod}
            options={PERIODS.filter((p) => p !== "MAX")}
          />
        </div>
      </header>

      <QueryState query={query} skeletonLines={8}>
        {(data) => <OverviewBody data={data} period={period} />}
      </QueryState>
    </div>
  );
}

function OverviewBody({ data, period }: { data: Overview; period: Period }) {
  const names = useMemo(() => {
    const m: Record<string, string> = {};
    for (const q of [...data.indices, ...data.snapshots, ...data.heatmap])
      m[q.instrument_id] = q.name;
    return m;
  }, [data]);

  const hasPrices = [...data.indices, ...data.snapshots].some((q) => q.price !== null);
  if (!hasPrices) {
    return (
      <EmptyState
        icon={<Clock size={28} aria-hidden="true" />}
        title="Market data has not loaded yet"
        description="The first data refresh has not finished. Prices appear here after the scheduled job runs; nothing on this page is made up in the meantime."
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <MarketBar data={data} />

      <section aria-labelledby="indices-h">
        <h2 id="indices-h" className="label mb-2">
          Indices
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {data.indices.map((q) => (
            <QuoteCard key={q.instrument_id} q={q} />
          ))}
        </div>
      </section>

      <section aria-labelledby="snap-h">
        <h2 id="snap-h" className="label mb-2">
          Crypto, metals and currency
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {data.snapshots.map((q) => (
            <QuoteCard key={q.instrument_id} q={q} />
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardHeader
            title="Performance comparison"
            subtitle={
              data.comparison.start
                ? `Growth of 100 since ${formatDate(data.comparison.start)}, total return in each index's own terms`
                : "Not enough overlapping history"
            }
          />
          {data.comparison.series.length ? (
            <LineChart
              caption="Growth of 100 comparison of major indices"
              baseline={100}
              format={(v) => formatNumber(v, 1)}
              series={data.comparison.series.map((s, i) => ({
                id: s.instrument_id,
                label: names[s.instrument_id] ?? s.instrument_id,
                color: seriesColor(i),
                points: s.points,
              }))}
            />
          ) : (
            <p className="text-muted">No overlapping history for this period.</p>
          )}
          {data.comparison.notes.map((n) => (
            <p key={n} className="mt-1 text-xs text-subtle">
              {n}
            </p>
          ))}
        </Card>

        <div className="flex flex-col gap-6 lg:col-span-4">
          <WatchlistCard currency={data.currency as "USD" | "INR"} />
          <Card>
            <CardHeader title="Top gainers" subtitle="Stocks and crypto" />
            {data.gainers.length ? (
              <ul>
                {data.gainers.map((q) => (
                  <MoverRow key={q.instrument_id} q={q} />
                ))}
              </ul>
            ) : (
              <p className="text-muted">Nothing rose over this period.</p>
            )}
          </Card>
          <Card>
            <CardHeader title="Top losers" subtitle="Stocks and crypto" />
            {data.losers.length ? (
              <ul>
                {data.losers.map((q) => (
                  <MoverRow key={q.instrument_id} q={q} />
                ))}
              </ul>
            ) : (
              <p className="text-muted">Nothing fell over this period.</p>
            )}
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader
          title="Stock heatmap"
          subtitle="Change by sector. Stronger colour means a bigger move."
        />
        <Heatmap quotes={data.heatmap} period={period} />
      </Card>
    </div>
  );
}

function MarketBar({ data }: { data: Overview }) {
  const ds = data.data_status;
  const ok = ds && (ds.status === "success" || ds.status === "partial");
  return (
    <Card className="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
      <ul className="flex flex-wrap gap-2" aria-label="Exchange status">
        {data.markets.map((m) => (
          <li
            key={m.session}
            className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs"
            title={m.name}
          >
            <span
              aria-hidden="true"
              className={
                m.open ? "size-1.5 rounded-full bg-positive" : "size-1.5 rounded-full bg-subtle"
              }
            />
            {m.session} <span className="text-muted">{m.open ? "Open" : "Closed"}</span>
          </li>
        ))}
      </ul>
      <div className="flex items-start gap-2 text-xs text-muted md:max-w-md md:text-right">
        {ds ? (
          ok ? (
            <CircleCheck size={14} className="mt-0.5 shrink-0 text-positive" aria-hidden="true" />
          ) : (
            <CircleAlert size={14} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          )
        ) : null}
        <span>
          {ds?.last_success_at
            ? `Last refresh ${formatDate(ds.last_success_at)} ${new Date(ds.last_success_at).toISOString().slice(11, 16)} UTC. `
            : ""}
          {ds?.status === "partial" ? `${ds.failed.length} instruments failed to refresh. ` : ""}
          {data.refresh_schedule}
        </span>
      </div>
    </Card>
  );
}
