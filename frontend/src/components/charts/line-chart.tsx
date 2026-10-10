"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart as RLineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate } from "@/lib/format";
import type { Point } from "@/lib/market";
import { Legend } from "./legend";
import { TableView } from "./table-view";

export type LineSeries = { id: string; label: string; color: string; points: Point[] };

function shortDate(iso: string, long: boolean) {
  const s = formatDate(iso);
  return long ? s.replace(/^\d+ /, "") : s.replace(/ \d{4}$/, "");
}

/**
 * Multi-series line chart on one y-axis, with crosshair tooltip, legend
 * (for 2+ series) and a table view.
 */
export function LineChart({
  series,
  format,
  height = 260,
  baseline,
  caption,
  domain,
  xFormat,
}: {
  series: LineSeries[];
  format: (v: number) => string;
  height?: number;
  baseline?: number;
  caption: string;
  domain?: [number | "auto", number | "auto"];
  /** Custom x labels (ticks, tooltip, table); defaults to dates. */
  xFormat?: (d: string) => string;
}) {
  const data = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    for (const s of series) {
      for (const p of s.points) {
        const row = byDate.get(p.date) ?? { date: p.date };
        row[s.id] = p.value;
        byDate.set(p.date, row);
      }
    }
    return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [series]);

  const spanDays =
    data.length > 1
      ? (Date.parse(String(data[data.length - 1].date)) - Date.parse(String(data[0].date))) / 864e5
      : 0;
  const long = spanDays > 400;
  const last = (s: LineSeries) => s.points[s.points.length - 1]?.value;

  return (
    <figure>
      <Legend
        items={series.map((s) => ({
          id: s.id,
          label: s.label,
          color: s.color,
          value: last(s) !== undefined ? format(last(s)!) : undefined,
        }))}
      />
      <div style={{ height }} role="img" aria-label={caption}>
        <ResponsiveContainer width="100%" height="100%">
          <RLineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => (xFormat ? xFormat(d) : shortDate(d, long))}
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              axisLine={{ stroke: "var(--chart-grid)" }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              tickFormatter={format}
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={64}
              domain={domain ?? ["auto", "auto"]}
            />
            {baseline !== undefined ? (
              <ReferenceLine y={baseline} stroke="var(--chart-axis)" strokeOpacity={0.6} />
            ) : null}
            <Tooltip
              cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm shadow-card">
                    <div className="mb-1 text-muted">{(xFormat ?? formatDate)(String(label))}</div>
                    {payload.map((p) => {
                      const s = series.find((x) => x.id === p.dataKey);
                      return (
                        <div key={String(p.dataKey)} className="flex items-center gap-2">
                          <span
                            aria-hidden="true"
                            className="inline-block size-2 rounded-full"
                            style={{ background: s?.color }}
                          />
                          <span className="text-muted">{s?.label}</span>
                          <span className="num ml-auto pl-3 font-medium">
                            {format(Number(p.value))}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : null
              }
            />
            {series.map((s) => (
              <Line
                key={s.id}
                type="linear"
                dataKey={s.id}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </RLineChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption={caption}
        columns={[xFormat ? "Step" : "Date", ...series.map((s) => s.label)]}
        rows={data.map((r) => [
          (xFormat ?? formatDate)(String(r.date)),
          ...series.map((s) => (typeof r[s.id] === "number" ? format(r[s.id] as number) : "—")),
        ])}
      />
    </figure>
  );
}
