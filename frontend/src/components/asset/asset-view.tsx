"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { LineChart } from "@/components/charts/line-chart";
import { PriceChart, type Overlay } from "@/components/charts/price-chart";
import { TableView } from "@/components/charts/table-view";
import { Card, CardHeader } from "@/components/ui/card";
import { Change } from "@/components/ui/change";
import { FreshnessChip } from "@/components/ui/freshness-chip";
import { WatchButton } from "@/components/watchlist/watch-button";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { abbreviate, formatDate, formatNumber, formatPercent, formatPrice } from "@/lib/format";
import {
  ASSET_CLASS_LABEL,
  PERIODS,
  assetHref,
  marketApi,
  toChip,
  type Detail,
  type DisplayCurrency,
  type Period,
} from "@/lib/market";
import { seriesColor } from "@/lib/series";
import { AnomaliesCard } from "./anomalies-card";
import { ForecastCard } from "./forecast-card";
import { FundamentalsPanel } from "./fundamentals";
import { NewsCard } from "./news-card";
import { RiskPanel } from "./risk-panel";

const OVERLAYS = [
  { key: "sma_50", label: "SMA 50" },
  { key: "sma_200", label: "SMA 200" },
  { key: "ema_20", label: "EMA 20" },
  { key: "bb", label: "Bollinger" },
] as const;
type OverlayKey = (typeof OVERLAYS)[number]["key"];

export function AssetView({ id }: { id: string }) {
  const [period, setPeriod] = useState<Period>("1Y");
  const [currency, setCurrency] = useState<DisplayCurrency | undefined>(undefined);
  const detail = useQuery({
    queryKey: ["detail", id, period, currency],
    queryFn: () => marketApi.detail(id, period, currency),
    placeholderData: (prev) => (prev?.instrument.id === id ? prev : undefined),
  });

  return (
    <QueryState query={detail} skeletonLines={10}>
      {(d) => (
        <div className="flex flex-col gap-6">
          <AssetHeader d={d} period={period} />
          <div className="flex flex-wrap gap-2">
            <Segmented
              label="Period"
              value={period}
              onChange={setPeriod}
              options={PERIODS.filter((p) => p !== "1D")}
            />
            {d.instrument.asset_class !== "index" && d.instrument.asset_class !== "fx" ? (
              <Segmented
                label="Display currency"
                value={currency ?? (d.instrument.currency as DisplayCurrency)}
                onChange={(c) => setCurrency(c === d.instrument.currency ? undefined : c)}
                options={["USD", "INR"] as const}
              />
            ) : null}
          </div>
          <PricePanel
            id={id}
            period={period}
            currency={currency}
            assetClass={d.instrument.asset_class}
          />
          <div className="grid gap-6 xl:grid-cols-12 [&>*]:min-w-0">
            <div className="xl:col-span-8">
              <div className="flex flex-col gap-6">
                <RiskPanel id={id} period={period} />
                <ForecastCard id={id} assetClass={d.instrument.asset_class} />
                <NewsCard id={id} />
                {d.instrument.asset_class === "equity" ? <FundamentalsPanel id={id} /> : null}
              </div>
            </div>
            <div className="flex flex-col gap-6 xl:col-span-4">
              <AboutCard d={d} />
              <AnomaliesCard id={id} />
              {d.snapshot ? <CryptoCard d={d} /> : null}
              {d.metal_context ? <MetalCard d={d} /> : null}
              <RelatedCard d={d} />
            </div>
          </div>
        </div>
      )}
    </QueryState>
  );
}

function AssetHeader({ d, period }: { d: Detail; period: Period }) {
  const { instrument: i, quote: q } = d;
  return (
    <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span>{ASSET_CLASS_LABEL[i.asset_class] ?? i.asset_class}</span>
          {i.exchange ? <span>· {i.exchange}</span> : null}
          <span>· {i.currency}</span>
          {d.market_open !== null ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-xs">
              <span
                aria-hidden="true"
                className={
                  d.market_open
                    ? "size-1.5 rounded-full bg-positive"
                    : "size-1.5 rounded-full bg-subtle"
                }
              />
              {d.market_open ? "Market open" : "Market closed"}
            </span>
          ) : null}
        </div>
        <h1 className="mt-1 text-xl font-semibold">{i.name}</h1>
      </div>
      <div className="flex flex-col items-start gap-1 md:items-end">
        <div className="flex items-baseline gap-3">
          <span className="text-2xl font-semibold">
            {q.price !== null ? formatPrice(q.price, q.currency, q.asset_class) : "—"}
          </span>
          <Change value={q.change_pct} />
          <span className="text-sm text-muted">{period === "MAX" ? "all history" : period}</span>
        </div>
        <div className="flex items-center gap-2">
          <FreshnessChip freshness={toChip(q.freshness)} />
          <WatchButton instrumentId={i.id} />
        </div>
      </div>
    </header>
  );
}

function PricePanel({
  id,
  period,
  currency,
  assetClass,
}: {
  id: string;
  period: Period;
  currency?: DisplayCurrency;
  assetClass: string;
}) {
  const [mode, setMode] = useState<"line" | "candle">("line");
  const [volume, setVolume] = useState(true);
  const [overlays, setOverlays] = useState<OverlayKey[]>([]);
  const history = useQuery({
    queryKey: ["history", id, period, currency],
    queryFn: () => marketApi.history(id, period, currency),
    placeholderData: (prev) => (prev?.instrument_id === id ? prev : undefined),
  });
  const indicators = useQuery({
    queryKey: ["indicators", id, period],
    queryFn: () => marketApi.indicators(id, period),
  });
  const converted = history.data?.converted ?? false;
  const ind = indicators.data?.series;

  const overlaySeries = useMemo<Overlay[]>(() => {
    if (!ind || converted) return [];
    const out: Overlay[] = [];
    overlays.forEach((k, idx) => {
      const color = seriesColor(idx + 1);
      if (k === "bb") {
        out.push({ id: "bb_upper", label: "BB upper", color, points: ind.bb_upper ?? [] });
        out.push({ id: "bb_lower", label: "BB lower", color, points: ind.bb_lower ?? [] });
      } else {
        out.push({
          id: k,
          label: OVERLAYS.find((o) => o.key === k)!.label,
          color,
          points: ind[k] ?? [],
        });
      }
    });
    return out;
  }, [ind, overlays, converted]);

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Segmented
          label="Chart type"
          value={mode}
          onChange={setMode}
          options={[
            { value: "line", label: "Line" },
            { value: "candle", label: "Candles" },
          ]}
        />
        <label className="inline-flex items-center gap-1.5 text-sm text-muted">
          <input
            type="checkbox"
            checked={volume}
            onChange={(e) => setVolume(e.target.checked)}
            className="accent-[var(--accent)]"
          />
          Volume
        </label>
        <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
        {OVERLAYS.map((o) => (
          <label key={o.key} className="inline-flex items-center gap-1.5 text-sm text-muted">
            <input
              type="checkbox"
              disabled={converted}
              checked={overlays.includes(o.key)}
              onChange={(e) =>
                setOverlays((cur) =>
                  e.target.checked ? [...cur, o.key] : cur.filter((k) => k !== o.key),
                )
              }
              className="accent-[var(--accent)]"
            />
            {o.label}
          </label>
        ))}
        {converted ? (
          <span className="text-xs text-subtle">Indicators use the original currency.</span>
        ) : null}
      </div>
      <QueryState query={history} skeletonLines={8}>
        {(h) =>
          h.bars.length ? (
            <>
              <PriceChart
                bars={h.bars}
                mode={mode}
                showVolume={volume}
                overlays={overlaySeries}
                format={(v) => formatPrice(v, h.currency, assetClass)}
                caption={`Price history, ${period}`}
              />
              <p className="mt-2 text-xs text-subtle">
                {h.source_note}
                {h.converted ? ` Converted to ${h.currency} at the daily USD/INR rate.` : ""}
                {h.retrieved_at ? ` Retrieved ${formatDate(h.retrieved_at)}.` : ""}
              </p>
              <TableView
                caption="Daily prices"
                columns={["Date", "Open", "High", "Low", "Close", "Volume"]}
                rows={h.bars.map((b) => [
                  formatDate(b.date),
                  ...[b.open, b.high, b.low, b.close].map((v) =>
                    v === null ? "—" : formatPrice(v, h.currency, assetClass),
                  ),
                  b.volume ? abbreviate(b.volume) : "—",
                ])}
              />
            </>
          ) : (
            <p className="py-10 text-center text-muted">No price history for this period.</p>
          )
        }
      </QueryState>
      {ind?.rsi_14?.length ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="label mb-2">RSI (14)</h3>
            <LineChart
              caption="Relative strength index, 14 days"
              height={150}
              domain={[0, 100]}
              format={(v) => formatNumber(v, 0)}
              series={[{ id: "rsi", label: "RSI", color: seriesColor(0), points: ind.rsi_14 }]}
            />
            <p className="mt-1 text-xs text-subtle">
              Above 70 is often read as overbought, below 30 as oversold.
            </p>
          </div>
          <div>
            <h3 className="label mb-2">MACD (12, 26, 9)</h3>
            <LineChart
              caption="MACD and signal line"
              height={150}
              baseline={0}
              format={(v) => formatNumber(v, 2)}
              series={[
                { id: "macd", label: "MACD", color: seriesColor(0), points: ind.macd ?? [] },
                {
                  id: "signal",
                  label: "Signal",
                  color: seriesColor(1),
                  points: ind.macd_signal ?? [],
                },
              ]}
            />
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-t border-border py-1.5 first:border-t-0">
      <dt className="text-muted">{k}</dt>
      <dd className="num text-right">{v}</dd>
    </div>
  );
}

function AboutCard({ d }: { d: Detail }) {
  const i = d.instrument;
  return (
    <Card>
      <CardHeader title="About" />
      <dl className="text-sm">
        {i.sector ? <Row k="Sector" v={i.sector} /> : null}
        {i.exchange ? <Row k="Exchange" v={i.exchange} /> : null}
        <Row k="Trading currency" v={i.currency} />
        <Row k="Time zone" v={i.timezone} />
        {i.price_definition ? <Row k="Price is" v={i.price_definition} /> : null}
      </dl>
    </Card>
  );
}

function CryptoCard({ d }: { d: Detail }) {
  const s = d.snapshot!;
  const usd = (v: number | null) => (v === null ? "—" : abbreviate(v, "USD"));
  const units = (v: number | null) => (v === null ? "—" : abbreviate(v));
  return (
    <Card>
      <CardHeader
        title="Market snapshot"
        subtitle={`${s.source_note}, as of ${formatDate(s.as_of)}`}
      />
      <dl className="text-sm">
        <Row k="Market cap" v={usd(s.market_cap)} />
        <Row k="24h volume" v={usd(s.volume_24h)} />
        <Row k="Circulating supply" v={units(s.circulating_supply)} />
        <Row k="Total supply" v={units(s.total_supply)} />
        <Row k="Max supply" v={s.max_supply === null ? "No cap" : units(s.max_supply)} />
      </dl>
    </Card>
  );
}

function MetalCard({ d }: { d: Detail }) {
  const m = d.metal_context!;
  return (
    <Card>
      <CardHeader title="Metals context" />
      <dl className="text-sm">
        {m.gold_silver_ratio !== null ? (
          <Row k="Gold/silver ratio" v={formatNumber(m.gold_silver_ratio, 1)} />
        ) : null}
        {m.inr_decomposition ? (
          <>
            <Row k="Return in USD" v={formatPercent(m.inr_decomposition.usd_return)} />
            <Row k="USD/INR change" v={formatPercent(m.inr_decomposition.fx_return)} />
            <Row k="Return in INR" v={formatPercent(m.inr_decomposition.inr_return)} />
          </>
        ) : null}
      </dl>
      {m.inr_decomposition ? (
        <p className="mt-2 text-xs text-subtle">{m.inr_decomposition.explanation}</p>
      ) : null}
      <p className="mt-2 text-xs text-subtle">
        Futures and ETF prices are not the same as Indian retail gold or silver rates, which add
        import duty, GST and dealer premiums.
      </p>
    </Card>
  );
}

function RelatedCard({ d }: { d: Detail }) {
  if (!d.related.length) return null;
  return (
    <Card>
      <CardHeader title="Related" />
      <ul className="text-sm">
        {d.related.map((r) => (
          <li key={r.id}>
            <Link
              href={assetHref(r.id)}
              className="flex justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-raised"
            >
              <span>{r.name}</span>
              <span className="text-muted">
                {ASSET_CLASS_LABEL[r.asset_class] ?? r.asset_class}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
