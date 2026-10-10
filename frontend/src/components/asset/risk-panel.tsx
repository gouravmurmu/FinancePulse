"use client";

import { useQuery } from "@tanstack/react-query";
import { Info, TriangleAlert } from "lucide-react";
import { LineChart } from "@/components/charts/line-chart";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { formatDate, formatNumber, formatPercent } from "@/lib/format";
import { marketApi, type InstrumentRisk, type Period } from "@/lib/market";
import { seriesColor } from "@/lib/series";

const LEVEL = {
  low: { label: "Low risk", cls: "text-positive border-positive/30" },
  moderate: { label: "Moderate risk", cls: "text-warning border-warning/40" },
  high: { label: "High risk", cls: "text-negative border-negative/40" },
} as const;

export function RiskBadge({ level }: { level: InstrumentRisk["risk_level"] }) {
  if (!level) return null;
  const l = LEVEL[level];
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${l.cls}`}>
      {l.label}
    </span>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-surface-raised px-3 py-2">
      <dt className="label">{label}</dt>
      <dd className="mt-0.5 text-md font-semibold">{value}</dd>
      {hint ? <dd className="text-xs text-subtle">{hint}</dd> : null}
    </div>
  );
}

const BENCHMARK_NAME: Record<string, string> = {
  "idx:us:SPX": "S&P 500",
  "idx:in:NIFTY50": "Nifty 50",
};

const pct = (v: number | null) => (v === null ? "—" : formatPercent(v));
const pctU = (v: number | null) => (v === null ? "—" : formatPercent(v, { signed: false }));
const num = (v: number | null) => (v === null ? "—" : formatNumber(v));

export function RiskPanel({ id, period }: { id: string; period: Period }) {
  const riskPeriod: Period = period === "1D" || period === "1W" ? "1Y" : period;
  const query = useQuery({
    queryKey: ["risk", id, riskPeriod],
    queryFn: () => marketApi.risk(id, riskPeriod),
    placeholderData: (prev) => prev,
  });
  return (
    <QueryState query={query}>
      {(r) => (
        <Card>
          <CardHeader
            title="Risk"
            subtitle={`${r.observations} daily returns, ${riskPeriod}${riskPeriod !== period ? " (short periods use 1Y)" : ""}`}
            action={<RiskBadge level={r.risk_level} />}
          />
          {r.warning ? (
            <p className="mb-3 flex gap-2 text-sm text-warning">
              <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" /> {r.warning}
            </p>
          ) : null}
          {r.insight ? <p className="mb-3 text-md">{r.insight}</p> : null}
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <Stat label="Total return" value={pct(r.metrics.total_return)} />
            <Stat label="CAGR" value={pct(r.metrics.cagr)} />
            <Stat label="Volatility" value={pctU(r.metrics.volatility)} hint="annualized" />
            <Stat label="Sharpe" value={num(r.metrics.sharpe)} hint="0% risk-free" />
            <Stat label="Sortino" value={num(r.metrics.sortino)} />
            <Stat
              label="Max drawdown"
              value={pct(r.metrics.max_drawdown)}
              hint={
                r.metrics.max_drawdown_trough
                  ? `trough ${formatDate(r.metrics.max_drawdown_trough)}${r.metrics.max_drawdown_recovery ? "" : ", not recovered"}`
                  : undefined
              }
            />
            <Stat
              label={`VaR ${Math.round(r.confidence * 100)}%`}
              value={pctU(r.metrics.var)}
              hint="1-day historical loss"
            />
            <Stat
              label="Exp. shortfall"
              value={pctU(r.metrics.expected_shortfall)}
              hint="avg loss beyond VaR"
            />
            {r.metrics.beta !== null ? (
              <Stat
                label="Beta"
                value={num(r.metrics.beta)}
                hint={`vs ${BENCHMARK_NAME[r.benchmark_id ?? ""] ?? "benchmark"}`}
              />
            ) : null}
          </dl>
          <div className="mt-5 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="label mb-2">Drawdown from peak</h3>
              <LineChart
                caption="Drawdown from previous peak"
                height={180}
                baseline={0}
                format={(v) => formatPercent(v)}
                series={[
                  { id: "dd", label: "Drawdown", color: seriesColor(0), points: r.drawdown },
                ]}
              />
            </div>
            <div>
              <h3 className="label mb-2">Rolling volatility</h3>
              <LineChart
                caption="Rolling annualized volatility"
                height={180}
                format={(v) => formatPercent(v, { signed: false })}
                series={[
                  {
                    id: "vol",
                    label: "Volatility",
                    color: seriesColor(0),
                    points: r.rolling_volatility,
                  },
                ]}
              />
            </div>
          </div>
          <details className="mt-4 text-sm text-muted">
            <summary className="inline-flex cursor-pointer items-center gap-1.5 hover:text-text">
              <Info size={14} aria-hidden="true" /> How these are calculated
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {r.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </details>
        </Card>
      )}
    </QueryState>
  );
}
