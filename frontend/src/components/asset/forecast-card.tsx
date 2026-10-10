"use client";

import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { formatDate, formatPercent, formatPrice } from "@/lib/format";
import { marketApi, type ForecastHorizon } from "@/lib/market";
import { useIsPro } from "@/lib/view-mode";

const HORIZON_LABEL: Record<number, string> = { 5: "1 week", 20: "1 month" };
const HORIZON_PHRASE: Record<number, string> = { 5: "one-week", 20: "one-month" };

const pct0 = (v: number) => `${Math.round(v * 100)}%`;

/** Stored baseline forecasts, always shown next to how well they did out of sample. */
export function ForecastCard({ id, assetClass }: { id: string; assetClass: string }) {
  const q = useQuery({ queryKey: ["forecast", id], queryFn: () => marketApi.forecast(id) });
  const [h, setH] = useState<string>("20");
  const pro = useIsPro();
  return (
    <Card>
      <CardHeader
        title="Forecast check"
        subtitle="Simple models, tested on past data before anything is shown"
        action={
          <InfoTip label="How forecasts are made and tested">
            Three models (no change, historical drift and damped-trend exponential smoothing) are
            refitted on two years of closes at 60 past dates and scored on what actually happened
            next. A model is only shown as useful if its errors were reliably smaller than simply
            assuming no change. Ranges cover 80% of past errors. Not advice.
          </InfoTip>
        }
      />
      <QueryState query={q} skeletonLines={4}>
        {(d) => {
          if (!d.available) {
            return <p className="text-sm text-muted">{d.reason ?? "Forecast unavailable."}</p>;
          }
          const run =
            d.horizons.find((x) => String(x.horizon_days) === h) ??
            d.horizons[d.horizons.length - 1];
          return (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Segmented
                  label="Horizon"
                  value={String(run.horizon_days)}
                  onChange={setH}
                  options={d.horizons.map((x) => ({
                    value: String(x.horizon_days),
                    label: HORIZON_LABEL[x.horizon_days] ?? `${x.horizon_days} days`,
                  }))}
                />
                <span className="text-xs text-subtle">
                  From the {formatDate(run.as_of)} close · {run.horizon_days} trading days
                </span>
              </div>
              {d.stale ? (
                <p className="text-xs text-warning">
                  This forecast is more than a week old; the forecast job may have failed.
                </p>
              ) : null}
              <Verdict run={run} currency={d.currency} assetClass={assetClass} />
              <RangeBar run={run} currency={d.currency} assetClass={assetClass} />
              {pro ? <ModelTable run={run} /> : null}
              <p className="text-xs text-subtle">
                Trained on closes from {formatDate(run.train_start)}. Tested on{" "}
                {run.models[0]?.n ?? 0} windows between {formatDate(run.eval_start)} and{" "}
                {formatDate(run.eval_end)}, each using only data available at the time. Model set{" "}
                {run.model_version}.
              </p>
            </div>
          );
        }}
      </QueryState>
    </Card>
  );
}

function Verdict({
  run,
  currency,
  assetClass,
}: {
  run: ForecastHorizon;
  currency: string;
  assetClass: string;
}) {
  const label = HORIZON_PHRASE[run.horizon_days] ?? `${run.horizon_days}-day`;
  const range = `${formatPrice(run.lower, currency, assetClass)} to ${formatPrice(run.upper, currency, assetClass)}`;
  if (!run.beats_baseline) {
    return (
      <div className="flex gap-3 rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
        <TriangleAlert size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-warning" />
        <div>
          <p className="font-medium">Model did not beat baseline</p>
          <p className="mt-1 text-muted">
            No model predicted {label} moves better than assuming the price stays where it is, so
            there is no forecast to show. Over past {label} windows the price usually ended between{" "}
            <span className="text-text">{range}</span> of a starting price like today&apos;s (80% of
            the time).
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-lg bg-surface-raised p-3 text-sm">
      <p>
        <span className="text-muted">{run.best_model_label} points to </span>
        <span className="text-lg font-semibold">
          {formatPrice(run.point, currency, assetClass)}
        </span>{" "}
        <span className="text-muted">
          ({run.change_pct !== null ? formatPercent(run.change_pct) : "—"}) over the next{" "}
          {run.horizon_days} trading days, with an 80% range of {range}.
        </span>
      </p>
      <p className="mt-1 text-xs text-muted">
        Its past errors were {run.skill !== null ? pct0(run.skill) : "—"} smaller than the no-change
        baseline. Ranges are wide because prices are hard to predict; treat this as one input, not a
        prediction you can rely on.
      </p>
    </div>
  );
}

function RangeBar({
  run,
  currency,
  assetClass,
}: {
  run: ForecastHorizon;
  currency: string;
  assetClass: string;
}) {
  const lo = Math.min(run.lower, run.last_close);
  const hi = Math.max(run.upper, run.last_close);
  const pad = (hi - lo) * 0.08 || 1;
  const min = lo - pad;
  const span = hi + pad - min;
  const pos = (v: number) => `${((v - min) / span) * 100}%`;
  return (
    <figure aria-label="Forecast range compared with the last close">
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-3.5 h-1 rounded-full bg-surface-raised" />
        <div
          className="absolute top-2.5 h-3 rounded-full bg-accent/30"
          style={{ left: pos(run.lower), width: `${((run.upper - run.lower) / span) * 100}%` }}
        />
        {run.beats_baseline ? (
          <div
            className="absolute top-1.5 h-5 w-0.5 bg-accent"
            style={{ left: pos(run.point) }}
            title="Model forecast"
          />
        ) : null}
        <div
          className="absolute top-1 h-6 w-0.5 bg-text"
          style={{ left: pos(run.last_close) }}
          title="Last close"
        />
      </div>
      <figcaption className="flex flex-wrap justify-between gap-2 text-xs text-muted">
        <span>Low {formatPrice(run.lower, currency, assetClass)}</span>
        <span>
          <span aria-hidden="true" className="mr-1 inline-block h-2.5 w-0.5 bg-text align-middle" />
          Last close {formatPrice(run.last_close, currency, assetClass)}
        </span>
        <span>High {formatPrice(run.upper, currency, assetClass)}</span>
      </figcaption>
    </figure>
  );
}

function ModelTable({ run }: { run: ForecastHorizon }) {
  const naive = run.models.find((m) => m.model === "naive");
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[440px] text-sm">
        <caption className="sr-only">Out-of-sample errors by model</caption>
        <thead>
          <tr className="text-left text-xs text-muted">
            <th className="py-1.5 pr-3 font-medium">Model</th>
            <th className="py-1.5 pr-3 text-right font-medium">
              <abbr title="Mean absolute error of the predicted move">Avg error</abbr>
            </th>
            <th className="py-1.5 pr-3 text-right font-medium">
              <abbr title="Root mean squared error, which weighs big misses more">RMSE</abbr>
            </th>
            <th className="py-1.5 pr-3 text-right font-medium">Right direction</th>
            <th className="py-1.5 text-right font-medium">
              <abbr title="Change in average error compared with assuming no change; negative is better">
                Error vs no change
              </abbr>
            </th>
          </tr>
        </thead>
        <tbody>
          {run.models.map((m) => {
            // Relative change in average error; negative means smaller errors than no change.
            const rel = naive && m.model !== "naive" ? m.mae / naive.mae - 1 : null;
            return (
              <tr key={m.model} className="border-t border-border">
                <td className="py-1.5 pr-3">
                  {m.label}
                  {m.model === run.best_model ? (
                    <span className="ml-1.5 rounded-full border border-accent/40 px-1.5 text-xs text-accent">
                      {run.beats_baseline ? "used" : "baseline"}
                    </span>
                  ) : null}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {formatPercent(m.mae, { signed: false })}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {formatPercent(m.rmse, { signed: false })}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {m.directional_accuracy !== null ? pct0(m.directional_accuracy) : "—"}
                </td>
                <td className="py-1.5 text-right tabular-nums">
                  {rel === null ? "—" : formatPercent(rel)}
                  {m.p_value !== null && m.p_value < (run.significance ?? 0.1) ? (
                    <span className="sr-only"> (reliable)</span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {run.up_share !== null ? (
        <p className="mt-1.5 text-xs text-subtle">
          For comparison, the price rose in {pct0(run.up_share)} of the test windows, so always
          guessing &quot;up&quot; would have been right that often.
        </p>
      ) : null}
    </div>
  );
}
