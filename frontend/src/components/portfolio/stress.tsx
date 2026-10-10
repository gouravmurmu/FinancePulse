"use client";

import { cn } from "@/lib/cn";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { formatMoney, formatPercent } from "@/lib/format";
import { marketApi } from "@/lib/market";
import { usePortfolioMutations, useSummary, type Portfolio, type Summary } from "@/lib/portfolio";
import { errorMessage, inputClass, primaryClass } from "./forms";

export function StressPanel({ portfolio }: { portfolio: Portfolio }) {
  const summary = useSummary(portfolio.id);
  return (
    <QueryState query={summary}>
      {(s) =>
        s.holdings.length ? (
          <Body portfolio={portfolio} s={s} />
        ) : (
          <p className="text-muted">Add holdings to run a stress test.</p>
        )
      }
    </QueryState>
  );
}

function Body({ portfolio, s }: { portfolio: Portfolio; s: Summary }) {
  const presets = useQuery({
    queryKey: ["stress-presets"],
    queryFn: marketApi.stressPresets,
    staleTime: Infinity,
  });
  const { stress } = usePortfolioMutations();
  const [shocks, setShocks] = useState<Record<string, string>>({});
  const ccy = s.base_currency;
  const names = Object.fromEntries(s.holdings.map((h) => [h.instrument_id, h.name]));
  const r = stress.data;

  function runCustom(e: React.FormEvent) {
    e.preventDefault();
    const parsed: Record<string, number> = {};
    for (const h of s.holdings) {
      const v = Number(shocks[h.instrument_id] ?? 0);
      parsed[h.instrument_id] = Number.isFinite(v) ? v / 100 : 0;
    }
    stress.mutate({ pid: portfolio.id, shocks: parsed });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader
            title="Scenarios"
            subtitle="Instant one-off price moves applied to today's holdings"
          />
          <div className="flex flex-col gap-2">
            {(presets.data ?? []).map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => stress.mutate({ pid: portfolio.id, preset: p.id })}
                disabled={stress.isPending}
                aria-pressed={r?.preset === p.id}
                className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-left text-sm hover:border-accent aria-pressed:border-accent disabled:opacity-50"
              >
                <span className="block font-medium">{p.label}</span>
                <span className="block text-xs text-muted">{p.description}</span>
              </button>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Your own shocks" subtitle="Percentage move per holding, e.g. −20" />
          <form onSubmit={runCustom} className="flex flex-col gap-2">
            {s.holdings.map((h) => (
              <label key={h.instrument_id} className="flex items-center gap-3 text-sm">
                <span className="flex-1 truncate">{h.name}</span>
                <input
                  inputMode="decimal"
                  aria-label={`Shock for ${h.name}, percent`}
                  value={shocks[h.instrument_id] ?? ""}
                  placeholder="0"
                  onChange={(e) => {
                    const t = e.target.value.replace("−", "-");
                    if (/^-?\d*\.?\d*$/.test(t)) setShocks((x) => ({ ...x, [h.instrument_id]: t }));
                  }}
                  className={cn(inputClass, "num w-24 text-right")}
                />
                <span className="text-muted">%</span>
              </label>
            ))}
            <button
              type="submit"
              className={`${primaryClass} mt-2 self-start`}
              disabled={stress.isPending}
            >
              Apply shocks
            </button>
          </form>
        </Card>
      </div>
      <Card>
        <CardHeader title="Result" />
        {stress.error ? (
          <p role="alert" className="text-sm text-negative">
            {errorMessage(stress.error)}
          </p>
        ) : null}
        {r ? (
          <div aria-live="polite">
            <p className="text-md">
              Your portfolio would {r.total < 0 ? "lose" : "gain"}{" "}
              <strong className={r.total < 0 ? "text-negative" : "text-positive"}>
                {formatMoney(Math.abs(r.pnl ?? 0), ccy)} ({formatPercent(r.total)})
              </strong>
              , from {formatMoney(r.value ?? 0, ccy)} to{" "}
              {formatMoney((r.value ?? 0) + (r.pnl ?? 0), ccy)}.
            </p>
            <table className="num mt-3 w-full text-sm">
              <caption className="sr-only">Stress test by holding</caption>
              <thead>
                <tr className="border-b border-border text-muted">
                  <th scope="col" className="py-1.5 text-left font-medium">
                    Holding
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    Weight
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    Shock
                  </th>
                  <th scope="col" className="py-1.5 text-right font-medium">
                    Effect ({ccy})
                  </th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(r.weights).map(([id, w]) => (
                  <tr key={id} className="border-b border-border">
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {names[id] ?? id}
                    </th>
                    <td className="py-1.5 text-right">{formatPercent(w, { signed: false })}</td>
                    <td className="py-1.5 text-right">
                      {r.shocks[id] !== undefined ? formatPercent(r.shocks[id]) : "none"}
                    </td>
                    <td className="py-1.5 text-right">
                      {formatMoney(r.contribution_amounts[id] ?? 0, ccy)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-subtle">{r.note}</p>
          </div>
        ) : (
          <p className="text-muted">Pick a scenario or enter your own shocks.</p>
        )}
      </Card>
    </div>
  );
}
