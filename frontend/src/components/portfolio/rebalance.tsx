"use client";

import { cn } from "@/lib/cn";
import { useMemo, useState } from "react";
import { Card, CardHeader } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { formatMoney, formatNumber, formatPercent } from "@/lib/format";
import { useSummary, type Holding, type Portfolio } from "@/lib/portfolio";
import { buttonClass, inputClass } from "./forms";

/** Hypothetical rebalancing: what to buy or sell to reach target weights.
 *  Nothing is traded; ignores fees and taxes. */
export function Rebalance({ portfolio }: { portfolio: Portfolio }) {
  const summary = useSummary(portfolio.id);
  return (
    <QueryState query={summary}>
      {(s) => {
        const priced = s.holdings.filter((h) => h.value_base && h.price);
        return priced.length ? (
          <Body holdings={priced} ccy={s.base_currency} />
        ) : (
          <p className="text-muted">Add priced holdings to plan a rebalance.</p>
        );
      }}
    </QueryState>
  );
}

function Body({ holdings, ccy }: { holdings: Holding[]; ccy: "USD" | "INR" }) {
  const current = useMemo(
    () =>
      Object.fromEntries(
        holdings.map((h) => [h.instrument_id, ((h.weight ?? 0) * 100).toFixed(1)]),
      ),
    [holdings],
  );
  const [targets, setTargets] = useState<Record<string, string>>(current);
  const [cash, setCash] = useState("");
  const total = holdings.reduce((a, h) => a + (h.value_base ?? 0), 0);
  const added = Number(cash) || 0;
  const newTotal = total + added;
  const sum = holdings.reduce((a, h) => a + (Number(targets[h.instrument_id]) || 0), 0);
  const valid = Math.abs(sum - 100) < 0.05;

  return (
    <Card>
      <CardHeader
        title="Rebalance planner"
        subtitle="Set target weights to see the trades needed. Hypothetical: nothing is traded, fees and taxes are ignored."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="label">New money to add ({ccy})</span>
          <input
            inputMode="decimal"
            value={cash}
            onChange={(e) => /^\d*\.?\d*$/.test(e.target.value) && setCash(e.target.value)}
            className={cn(inputClass, "num w-40")}
            placeholder="0"
          />
        </label>
        <button
          type="button"
          className={buttonClass}
          onClick={() => {
            const eq = (100 / holdings.length).toFixed(2);
            setTargets(Object.fromEntries(holdings.map((h) => [h.instrument_id, eq])));
          }}
        >
          Equal weights
        </button>
        <button type="button" className={buttonClass} onClick={() => setTargets(current)}>
          Reset to current
        </button>
      </div>
      <div className="-mx-4 overflow-x-auto">
        <table className="num w-full min-w-[640px] text-sm">
          <caption className="sr-only">Rebalancing trades</caption>
          <thead>
            <tr className="border-b border-border text-muted">
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Holding
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Current
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Target %
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Trade ({ccy})
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Approx. quantity
              </th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => {
              const target = (Number(targets[h.instrument_id]) || 0) / 100;
              const trade = target * newTotal - (h.value_base ?? 0);
              // price in base currency per displayed unit
              const unitValue = (h.value_base ?? 0) / h.quantity;
              const qty = unitValue ? trade / unitValue : 0;
              return (
                <tr key={h.instrument_id} className="border-b border-border">
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {h.name}
                  </th>
                  <td className="px-3 py-2 text-right">
                    {formatPercent(h.weight ?? 0, { signed: false })}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <input
                      inputMode="decimal"
                      aria-label={`Target weight for ${h.name}, percent`}
                      value={targets[h.instrument_id] ?? ""}
                      onChange={(e) =>
                        /^\d*\.?\d*$/.test(e.target.value) &&
                        setTargets((t) => ({ ...t, [h.instrument_id]: e.target.value }))
                      }
                      className={cn(inputClass, "num w-20 py-1 text-right")}
                    />
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-medium ${!valid ? "text-subtle" : trade > 0.5 ? "text-positive" : trade < -0.5 ? "text-negative" : ""}`}
                  >
                    {!valid
                      ? "—"
                      : Math.abs(trade) < 0.5
                        ? "No trade"
                        : `${trade > 0 ? "▲ Buy" : "▼ Sell"} ${formatMoney(Math.abs(trade), ccy)}`}
                  </td>
                  <td className="px-3 py-2 text-right text-muted">
                    {!valid || Math.abs(trade) < 0.5
                      ? "—"
                      : `${formatNumber(Math.abs(qty), Math.abs(qty) < 1 ? 4 : 2)}${h.unit === "gram" ? " g" : h.unit === "troy_oz" ? " oz t" : ""}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={`mt-3 text-sm ${valid ? "text-muted" : "text-warning"}`} role="status">
        Targets add up to {formatNumber(sum, 1)}%{valid ? "." : ". Adjust them to total 100%."}
      </p>
    </Card>
  );
}
