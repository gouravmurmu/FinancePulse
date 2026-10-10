"use client";

import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { LineChart } from "@/components/charts/line-chart";
import { CorrelationMatrix } from "@/components/risk/correlation-matrix";
import { Card, CardHeader } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { formatDate, formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { usePerformance, type Performance, type Portfolio } from "@/lib/portfolio";
import { seriesColor } from "@/lib/series";

const PERIODS = ["1M", "3M", "6M", "YTD", "1Y", "3Y", "MAX"] as const;
type P = (typeof PERIODS)[number];

const pct = (v: number | null) => (v == null ? "—" : formatPercent(v));
const pctU = (v: number | null) => (v == null ? "—" : formatPercent(v, { signed: false }));
const num = (v: number | null) => (v == null ? "—" : formatNumber(v));

function Stat({ label, value, tip }: { label: string; value: string; tip: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-surface-raised px-3 py-2">
      <dt className="label flex items-center gap-1">
        {label} <InfoTip label={label}>{tip}</InfoTip>
      </dt>
      <dd className="num mt-0.5 text-md font-semibold">{value}</dd>
    </div>
  );
}

export function PerformancePanel({ portfolio }: { portfolio: Portfolio }) {
  const [period, setPeriod] = useState<P>("1Y");
  const query = usePerformance(portfolio.id, period, portfolio.transaction_count > 0);
  if (portfolio.transaction_count === 0) {
    return <p className="text-muted">Add transactions to see performance.</p>;
  }
  return (
    <div className="flex flex-col gap-6">
      <Segmented label="Period" options={PERIODS} value={period} onChange={setPeriod} />
      <QueryState query={query} skeletonLines={10}>
        {(p) => <Body p={p} />}
      </QueryState>
    </div>
  );
}

function Body({ p }: { p: Performance }) {
  const m = p.metrics;
  const ccy = p.base_currency;
  const series = [
    { id: "portfolio", label: "Your portfolio", color: seriesColor(0), points: p.portfolio },
    ...(p.benchmark.points.length
      ? [
          {
            id: "benchmark",
            label: p.benchmark.name ?? "Benchmark",
            color: seriesColor(1),
            points: p.benchmark.points,
          },
        ]
      : []),
  ];
  const names = Object.fromEntries(
    (p.correlation?.ids ?? []).map((id, i) => [id, p.correlation!.names[i]]),
  );
  return (
    <>
      {p.insight ? <p className="text-md">{p.insight}</p> : null}
      {p.warning ? (
        <p className="flex items-center gap-2 text-sm text-warning" role="status">
          <TriangleAlert size={14} aria-hidden="true" /> {p.warning}
        </p>
      ) : null}
      <Card>
        <CardHeader
          title="Performance vs benchmark"
          subtitle={`Growth of 100 from ${formatDate(p.portfolio[0]?.date ?? p.start)}, time-weighted, in ${ccy}`}
        />
        <LineChart
          series={series}
          format={(v) => formatNumber(v, 1)}
          baseline={100}
          caption="Portfolio growth of 100 compared with its benchmark"
        />
        <p className="mt-2 text-xs text-subtle">
          End-of-day closes to {formatDate(p.end)}. Benchmark: {p.benchmark.name ?? "none"}, price
          index in its own currency.
        </p>
      </Card>

      <Card>
        <CardHeader title="Return and risk" subtitle={`${p.observations} daily returns`} />
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Return"
            value={pct(m.time_weighted_return)}
            tip="Time-weighted return: how the investments performed, ignoring when you added or withdrew money."
          />
          <Stat
            label="Benchmark"
            value={pct(m.benchmark_return)}
            tip="The benchmark's price change over the same dates."
          />
          <Stat
            label="Volatility"
            value={pctU(m.volatility)}
            tip="Annualized standard deviation of daily returns. Higher means bigger swings in both directions."
          />
          <Stat
            label="Sharpe ratio"
            value={num(m.sharpe)}
            tip="Annualized return per unit of volatility (0% risk-free rate). Higher = more return for the risk taken."
          />
          <Stat
            label="Max drawdown"
            value={pct(m.max_drawdown)}
            tip="Largest fall from a peak to a later low in this period."
          />
          <Stat
            label="1-day VaR 95%"
            value={pctU(m.var)}
            tip="On 95% of past days the loss was smaller than this. On the worst 5% it was larger. Historical, not a forecast."
          />
          <Stat
            label="Beta"
            value={num(m.beta)}
            tip="How much the portfolio tended to move when the benchmark moved 1%. Above 1 = amplifies the market."
          />
          <Stat
            label="Value now"
            value={p.value.length ? formatMoney(p.value[p.value.length - 1].value, ccy) : "—"}
            tip="Market value at the latest close, in your base currency."
          />
        </dl>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <Card>
          <CardHeader title="Drawdown" subtitle="Distance below the previous peak" />
          <LineChart
            series={[{ id: "dd", label: "Drawdown", color: seriesColor(0), points: p.drawdown }]}
            format={(v) => formatPercent(v)}
            height={200}
            caption="Portfolio drawdown from its running peak"
          />
        </Card>
        <Card>
          <CardHeader
            title="Where the risk comes from"
            subtitle="Each holding's share of portfolio variance, last 12 months"
          />
          <RiskTable p={p} />
        </Card>
      </div>

      {p.correlation ? (
        <Card>
          <CardHeader
            title="Correlation between holdings"
            subtitle="Daily returns in base currency, last 12 months"
          />
          <CorrelationMatrix ids={p.correlation.ids} matrix={p.correlation.matrix} names={names} />
        </Card>
      ) : null}

      <ul className="flex flex-col gap-1 text-xs text-subtle">
        {p.assumptions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </>
  );
}

function RiskTable({ p }: { p: Performance }) {
  const rows = [...p.risk].sort(
    (a, b) => (b.risk_contribution ?? b.weight ?? 0) - (a.risk_contribution ?? a.weight ?? 0),
  );
  return (
    <table className="num w-full text-sm">
      <caption className="sr-only">Risk contribution by holding</caption>
      <thead>
        <tr className="border-b border-border text-muted">
          <th scope="col" className="py-1.5 text-left font-medium">
            Holding
          </th>
          <th scope="col" className="py-1.5 text-right font-medium">
            Weight
          </th>
          <th scope="col" className="py-1.5 text-right font-medium">
            Volatility
          </th>
          <th scope="col" className="py-1.5 text-right font-medium">
            Share of risk
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.instrument_id} className="border-b border-border">
            <th scope="row" className="py-1.5 text-left font-normal">
              {r.name}
            </th>
            <td className="py-1.5 text-right">{pctU(r.weight)}</td>
            <td className="py-1.5 text-right">{pctU(r.volatility)}</td>
            <td className="py-1.5 text-right font-medium">
              {r.risk_contribution == null
                ? "—"
                : formatPercent(r.risk_contribution, { signed: false })}
              {r.weight != null &&
              r.risk_contribution != null &&
              r.risk_contribution > r.weight * 1.5 ? (
                <span className="ml-1 text-xs text-warning">outsized</span>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
