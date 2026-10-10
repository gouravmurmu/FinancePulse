"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Info, Play } from "lucide-react";
import { useMemo, useState } from "react";
import { Histogram } from "@/components/charts/histogram";
import { LineChart } from "@/components/charts/line-chart";
import { RiskBadge } from "@/components/asset/risk-panel";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { ErrorState, SkeletonCard } from "@/components/ui/states";
import { ApiError } from "@/lib/api";
import { abbreviate, formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { marketApi, type Instrument, type Period, type RiskLab as RiskLabData } from "@/lib/market";
import { assignSlots, seriesColor } from "@/lib/series";
import { CorrelationMatrix } from "./correlation-matrix";
import { InstrumentPicker } from "./instrument-picker";

const DEFAULT = ["idx:us:SPX", "idx:in:NIFTY50", "crypto:BTC", "metal:XAU:comex-fut"];
const DEFAULT_NAMES: Record<string, string> = {
  "idx:us:SPX": "S&P 500",
  "idx:in:NIFTY50": "Nifty 50",
  "crypto:BTC": "Bitcoin",
  "metal:XAU:comex-fut": "Gold COMEX futures",
};
const LAB_PERIODS = ["3M", "6M", "YTD", "1Y", "3Y", "5Y"] as const;

function errorText(e: unknown): string {
  return e instanceof ApiError
    ? e.message
    : "The analytics server did not respond. Try again in a moment.";
}

export function RiskLab() {
  const [selected, setSelected] = useState<string[]>(DEFAULT);
  const [slots, setSlots] = useState<Record<string, number>>(() => assignSlots(DEFAULT));
  const [names, setNames] = useState<Record<string, string>>(DEFAULT_NAMES);
  const [period, setPeriod] = useState<Period>("1Y");
  const [confidence, setConfidence] = useState("0.95");
  const weights = useWeights(selected);

  function add(i: Instrument) {
    const next = [...selected, i.id];
    setSelected(next);
    setSlots((s) => assignSlots(next, s));
    setNames((n) => ({ ...n, [i.id]: i.name }));
  }
  function remove(id: string) {
    const next = selected.filter((x) => x !== id);
    setSelected(next);
    setSlots((s) => assignSlots(next, s));
  }

  const analysis = useQuery({
    queryKey: ["risk-lab", selected, period, confidence],
    queryFn: () =>
      marketApi.riskLab({ instrument_ids: selected, period, confidence: Number(confidence) }),
    enabled: selected.length >= 2,
    placeholderData: (prev) => prev,
  });

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">Risk Lab</h1>
        <p className="mt-1 max-w-prose text-muted">
          Compare how risky assets have been, how they move together, and what a mix of them could
          do. Everything is based on past daily prices; none of it is a forecast.
        </p>
      </header>

      <Card className="flex flex-col gap-3">
        <InstrumentPicker
          selected={selected}
          slots={slots}
          names={names}
          onAdd={add}
          onRemove={remove}
        />
        <div className="flex flex-wrap gap-2">
          <Segmented label="Period" value={period} onChange={setPeriod} options={LAB_PERIODS} />
          <Segmented
            label="VaR confidence"
            value={confidence}
            onChange={setConfidence}
            options={[
              { value: "0.9", label: "90%" },
              { value: "0.95", label: "95%" },
              { value: "0.99", label: "99%" },
            ]}
          />
        </div>
      </Card>

      {selected.length < 2 ? (
        <Card>
          <p className="text-muted">Add at least two instruments to compare.</p>
        </Card>
      ) : (
        <QueryState query={analysis} skeletonLines={10}>
          {(data) => <Analysis data={data} slots={slots} names={names} />}
        </QueryState>
      )}

      <MonteCarloCard selected={selected} names={names} w={weights} />
      <StressCard selected={selected} names={names} w={weights} />
    </div>
  );
}

function Analysis({
  data,
  slots,
  names,
}: {
  data: RiskLabData;
  slots: Record<string, number>;
  names: Record<string, string>;
}) {
  const label = (id: string) =>
    names[id] ?? data.metrics.find((m) => m.instrument_id === id)?.name ?? id;
  const allNames = Object.fromEntries(
    data.metrics.map((m) => [m.instrument_id, label(m.instrument_id)]),
  );
  const pct = (v: number | null, signed = true) =>
    v === null ? "—" : formatPercent(v, { signed });
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader
          title="Risk comparison"
          subtitle={`${formatDate(data.start)} to ${formatDate(data.end)} · ${data.observations} common trading days`}
        />
        {data.insight ? <p className="mb-3 text-md">{data.insight}</p> : null}
        <div className="overflow-x-auto">
          <table className="num w-full text-sm">
            <caption className="sr-only">Risk metrics per instrument</caption>
            <thead>
              <tr className="text-left text-xs text-muted">
                <th scope="col" className="py-2 pr-3 font-medium">
                  Instrument
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Return
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Volatility
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Sharpe
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Sortino
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Max drawdown
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  VaR {Math.round(data.confidence * 100)}%
                </th>
                <th scope="col" className="px-3 text-right font-medium">
                  Exp. shortfall
                </th>
                <th scope="col" className="pl-3 font-medium">
                  Risk
                </th>
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m) => (
                <tr key={m.instrument_id} className="border-t border-border">
                  <th scope="row" className="py-2 pr-3 text-left font-medium">
                    <span className="inline-flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="size-2 shrink-0 rounded-full"
                        style={{ background: seriesColor(slots[m.instrument_id] ?? 0) }}
                      />
                      {label(m.instrument_id)}
                    </span>
                  </th>
                  <td className="px-3 text-right">{pct(m.total_return)}</td>
                  <td className="px-3 text-right">{pct(m.volatility, false)}</td>
                  <td className="px-3 text-right">
                    {m.sharpe === null ? "—" : formatNumber(m.sharpe)}
                  </td>
                  <td className="px-3 text-right">
                    {m.sortino === null ? "—" : formatNumber(m.sortino)}
                  </td>
                  <td className="px-3 text-right">{pct(m.max_drawdown)}</td>
                  <td className="px-3 text-right">{pct(m.var, false)}</td>
                  <td className="px-3 text-right">{pct(m.expected_shortfall, false)}</td>
                  <td className="pl-3">
                    <RiskBadge level={m.risk_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Assumptions items={data.assumptions} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Correlation" subtitle="How daily returns moved together" />
          <CorrelationMatrix
            ids={data.correlation.ids}
            matrix={data.correlation.matrix}
            names={allNames}
          />
        </Card>
        <Card>
          <CardHeader
            title="Rolling correlation"
            subtitle={`${label(data.rolling_correlation.pair[0])} vs ${label(data.rolling_correlation.pair[1])}, ${data.window}-day window`}
          />
          {data.rolling_correlation.points.length ? (
            <LineChart
              caption="Rolling correlation of the first two instruments"
              height={220}
              baseline={0}
              domain={[-1, 1]}
              format={(v) => formatNumber(v)}
              series={[
                {
                  id: "rc",
                  label: "Correlation",
                  color: seriesColor(0),
                  points: data.rolling_correlation.points,
                },
              ]}
            />
          ) : (
            <p className="text-muted">Choose a longer period to see rolling correlation.</p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Drawdowns" subtitle="Fall from the previous peak" />
        <LineChart
          caption="Drawdown from previous peak per instrument"
          baseline={0}
          format={(v) => formatPercent(v)}
          series={data.correlation.ids.map((id) => ({
            id,
            label: label(id),
            color: seriesColor(slots[id] ?? 0),
            points: data.drawdowns[id] ?? [],
          }))}
        />
      </Card>
    </div>
  );
}

function Assumptions({ items }: { items: string[] }) {
  return (
    <details className="mt-4 text-sm text-muted">
      <summary className="inline-flex cursor-pointer items-center gap-1.5 hover:text-text">
        <Info size={14} aria-hidden="true" /> Assumptions
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {items.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </details>
  );
}

const HORIZONS = [
  { value: "21", label: "1 month" },
  { value: "126", label: "6 months" },
  { value: "252", label: "1 year" },
  { value: "756", label: "3 years" },
] as const;

function useWeights(selected: string[]) {
  const [raw, setRaw] = useState<Record<string, string>>({});
  const weights = useMemo(() => {
    const out: Record<string, number> = {};
    for (const id of selected) {
      const v = Number(raw[id] ?? 100 / selected.length);
      out[id] = Number.isFinite(v) && v >= 0 ? v : 0;
    }
    return out;
  }, [raw, selected]);
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  return { raw, setRaw, weights, total };
}

function WeightInputs({
  selected,
  names,
  w,
}: {
  selected: string[];
  names: Record<string, string>;
  w: ReturnType<typeof useWeights>;
}) {
  return (
    <fieldset className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <legend className="label mb-2">Weights (%)</legend>
      {selected.map((id) => (
        <label
          key={id}
          className="flex items-center justify-between gap-2 rounded-lg bg-surface-raised px-3 py-1.5 text-sm"
        >
          <span className="truncate">{names[id] ?? id}</span>
          <input
            type="number"
            min={0}
            step={5}
            inputMode="decimal"
            value={w.raw[id] ?? formatNumber(100 / selected.length, 0)}
            onChange={(e) => w.setRaw((r) => ({ ...r, [id]: e.target.value }))}
            className="num w-16 rounded border border-border bg-surface px-1.5 py-0.5 text-right"
          />
        </label>
      ))}
      <p className="text-xs text-subtle sm:col-span-2 lg:col-span-4">
        Total {formatNumber(w.total, 0)}%. Weights are scaled to 100%.
      </p>
    </fieldset>
  );
}

type Weights = ReturnType<typeof useWeights>;

function MonteCarloCard({
  selected,
  names,
  w,
}: {
  selected: string[];
  names: Record<string, string>;
  w: Weights;
}) {
  const [horizon, setHorizon] = useState("252");
  const [initial, setInitial] = useState("10000");
  const [lookback, setLookback] = useState<Period>("3Y");
  const mc = useMutation({
    mutationFn: () =>
      marketApi.monteCarlo({
        weights: w.weights,
        initial_value: Number(initial) || 10000,
        horizon_days: Number(horizon),
        paths: 2000,
        seed: 42,
        lookback,
      }),
  });
  const r = mc.data;
  const money = (v: number) => formatMoney(v, "USD", 0);

  return (
    <Card>
      <CardHeader
        title="Monte Carlo simulation"
        subtitle="2,000 simulated paths for a mix of the selected assets"
      />
      {selected.length === 0 ? (
        <p className="text-muted">Add instruments above.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <WeightInputs selected={selected} names={names} w={w} />
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="label">Starting value ($)</span>
              <input
                type="number"
                min={1}
                value={initial}
                onChange={(e) => setInitial(e.target.value)}
                className="num w-32 rounded-lg border border-border bg-surface px-2 py-1"
              />
            </label>
            <div className="flex flex-col gap-1">
              <span className="label">Horizon</span>
              <Segmented label="Horizon" value={horizon} onChange={setHorizon} options={HORIZONS} />
            </div>
            <div className="flex flex-col gap-1">
              <span className="label">Learn from</span>
              <Segmented
                label="Look-back"
                value={lookback}
                onChange={setLookback}
                options={["1Y", "3Y", "5Y"] as const}
              />
            </div>
            <button
              type="button"
              onClick={() => mc.mutate()}
              disabled={mc.isPending || w.total <= 0}
              className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-50"
            >
              <Play size={14} aria-hidden="true" />{" "}
              {mc.isPending ? "Simulating…" : "Run simulation"}
            </button>
          </div>
          {mc.isPending && !r ? <SkeletonCard lines={6} /> : null}
          {mc.isError ? (
            <ErrorState description={errorText(mc.error)} onRetry={() => mc.mutate()} />
          ) : null}
          {r ? (
            <div className="flex flex-col gap-4" style={{ opacity: mc.isPending ? 0.6 : 1 }}>
              <p className="text-md">
                In {formatPercent(r.probability_of_loss, { signed: false })} of simulated paths the
                mix ended below {money(r.initial_value)}. The middle outcome was{" "}
                {money(r.final.p50)}; 90% of paths ended between {money(r.final.p5)} and{" "}
                {money(r.final.p95)}.
              </p>
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="label mb-2">Range of paths</h3>
                  <LineChart
                    caption="Simulated portfolio value percentiles over time"
                    height={240}
                    baseline={r.initial_value}
                    format={(v) => abbreviate(v, "USD")}
                    xFormat={dayLabel}
                    series={[
                      { key: "95", label: "95th percentile", slot: 2 },
                      { key: "50", label: "Median", slot: 0 },
                      { key: "5", label: "5th percentile", slot: 1 },
                    ].map((p) => ({
                      id: `p${p.key}`,
                      label: p.label,
                      color: seriesColor(p.slot),
                      points: dayPoints(r.percentiles[p.key] ?? []),
                    }))}
                  />
                </div>
                <div>
                  <h3 className="label mb-2">Where paths ended</h3>
                  <Histogram
                    caption="Distribution of final simulated values"
                    bins={r.histogram}
                    format={(v) => abbreviate(v, "USD")}
                    marker={{ value: r.initial_value, label: "Start" }}
                  />
                </div>
              </div>
              <p className="text-xs text-subtle">
                Inputs estimated from {r.estimation_window.observations} days (
                {formatDate(r.estimation_window.start)} to {formatDate(r.estimation_window.end)}).
                Seed {r.seed}, so the same inputs give the same result.
              </p>
              <Assumptions items={r.assumptions} />
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}

/**
 * Percentile arrays are indexed by trading day. The chart keys rows by ISO
 * date, so day N is encoded as BASE + N days and labelled "Day N".
 */
const BASE = Date.UTC(2000, 0, 1);
function dayLabel(iso: string): string {
  return `Day ${Math.round((Date.parse(iso) - BASE) / 864e5)}`;
}
function dayPoints(values: number[]) {
  const step = Math.max(1, Math.floor(values.length / 200));
  const base = BASE;
  return values
    .filter((_, i) => i % step === 0 || i === values.length - 1)
    .map((v, k, arr) => {
      const day = k === arr.length - 1 ? values.length - 1 : k * step;
      return { date: new Date(base + day * 864e5).toISOString().slice(0, 10), value: v };
    });
}

function StressCard({
  selected,
  names,
  w,
}: {
  selected: string[];
  names: Record<string, string>;
  w: Weights;
}) {
  const presets = useQuery({
    queryKey: ["stress-presets"],
    queryFn: marketApi.stressPresets,
    staleTime: Infinity,
  });
  const stress = useMutation({
    mutationFn: (preset: string) => marketApi.stress({ weights: w.weights, preset }),
  });
  const r = stress.data;
  return (
    <Card>
      <CardHeader title="Stress test" subtitle="An instant one-off shock to the same mix" />
      {selected.length === 0 ? (
        <p className="text-muted">Add instruments above.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted">Uses the weights set in the simulation above.</p>
          <div className="flex flex-wrap gap-2">
            {(presets.data ?? []).map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => stress.mutate(p.id)}
                disabled={stress.isPending || w.total <= 0}
                aria-pressed={r?.preset === p.id}
                className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-left text-sm hover:border-accent aria-pressed:border-accent disabled:opacity-50"
              >
                <span className="block font-medium">{p.label}</span>
                <span className="block text-xs text-muted">{p.description}</span>
              </button>
            ))}
          </div>
          {stress.isError ? <ErrorState description={errorText(stress.error)} /> : null}
          {r ? (
            <div>
              <p className="text-md">
                The mix would move{" "}
                <strong className={r.total < 0 ? "text-negative" : "text-positive"}>
                  {formatPercent(r.total)}
                </strong>
                .
              </p>
              <table className="num mt-2 w-full text-sm">
                <caption className="sr-only">Stress test contributions</caption>
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th scope="col" className="py-1.5 font-medium">
                      Instrument
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Weight
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Shock
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Effect on mix
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(r.weights).map(([id, wt]) => (
                    <tr key={id} className="border-t border-border">
                      <th scope="row" className="py-1.5 text-left font-normal">
                        {names[id] ?? id}
                      </th>
                      <td className="text-right">{formatPercent(wt, { signed: false })}</td>
                      <td className="text-right">
                        {r.shocks[id] !== undefined ? formatPercent(r.shocks[id]) : "none"}
                      </td>
                      <td className="text-right">{formatPercent(r.contributions[id] ?? 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-subtle">{r.note}</p>
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}
