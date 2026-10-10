"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { seriesColor } from "@/lib/series";
import { TableView } from "./table-view";

export type DonutSlice = { label: string; value: number; weight: number };

/**
 * Allocation donut (at most 6 slices; the API groups the rest as "Other")
 * with a ranked bar list beside it that carries every number, so colour is
 * never the only key.
 */
export function Donut({
  slices,
  format,
  caption,
}: {
  slices: DonutSlice[];
  format: (v: number) => string;
  caption: string;
}) {
  const pct = (w: number) => `${(w * 100).toFixed(1)}%`;
  return (
    <figure className="@container">
      <div className="grid items-center gap-4 @md:grid-cols-[160px_1fr]">
        <div className="mx-auto size-40" role="img" aria-label={caption}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius="62%"
                outerRadius="100%"
                paddingAngle={slices.length > 1 ? 1.5 : 0}
                stroke="var(--surface)"
                isAnimationActive={false}
              >
                {slices.map((s, i) => (
                  <Cell key={s.label} fill={seriesColor(i)} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm shadow-card">
                      <div className="text-muted">{String(payload[0].name)}</div>
                      <div className="num font-medium">
                        {format(Number(payload[0].value))} ·{" "}
                        {pct((payload[0].payload as DonutSlice).weight)}
                      </div>
                    </div>
                  ) : null
                }
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ol className="flex flex-col gap-2" aria-label={`${caption}, ranked`}>
          {slices.map((s, i) => (
            <li key={s.label} className="text-sm">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block size-2.5 shrink-0 rounded-sm"
                  style={{ background: seriesColor(i) }}
                />
                <span className="truncate">{s.label}</span>
                <span className="num ml-auto text-muted">{format(s.value)}</span>
                <span className="num w-14 text-right font-medium">{pct(s.weight)}</span>
              </div>
              <div className="ml-4.5 mt-1 h-1.5 rounded-full bg-surface-raised">
                <div
                  className="h-1.5 rounded-full"
                  style={{ width: pct(s.weight), background: seriesColor(i) }}
                />
              </div>
            </li>
          ))}
        </ol>
      </div>
      <TableView
        caption={caption}
        columns={["Slice", "Value", "Weight"]}
        rows={slices.map((s) => [s.label, format(s.value), pct(s.weight)])}
      />
    </figure>
  );
}
