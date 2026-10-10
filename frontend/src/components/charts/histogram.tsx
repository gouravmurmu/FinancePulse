"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TableView } from "./table-view";

export type Bin = { from: number; to: number; count: number };

export function Histogram({
  bins,
  format,
  caption,
  marker,
  height = 220,
}: {
  bins: Bin[];
  format: (v: number) => string;
  caption: string;
  marker?: { value: number; label: string };
  height?: number;
}) {
  const data = bins.map((b) => ({ ...b, mid: (b.from + b.to) / 2 }));
  return (
    <figure>
      <div style={{ height }} role="img" aria-label={caption}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            barCategoryGap={2}
            margin={{ top: 16, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="mid"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={format}
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              axisLine={{ stroke: "var(--chart-grid)" }}
              tickLine={false}
              minTickGap={30}
            />
            <YAxis
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            {marker ? (
              <ReferenceLine
                x={marker.value}
                stroke="var(--text-muted)"
                label={{
                  value: marker.label,
                  fill: "var(--text-muted)",
                  fontSize: 12,
                  position: "top",
                }}
              />
            ) : null}
            <Tooltip
              cursor={{ fill: "var(--chart-grid)" }}
              content={({ active, payload }) => {
                const b = active ? (payload?.[0]?.payload as Bin | undefined) : undefined;
                return b ? (
                  <div className="num rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm shadow-card">
                    {format(b.from)} to {format(b.to)}: <strong>{b.count}</strong> paths
                  </div>
                ) : null;
              }}
            />
            <Bar
              dataKey="count"
              fill="var(--chart-1)"
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <TableView
        caption={caption}
        columns={["From", "To", "Paths"]}
        rows={bins.map((b) => [format(b.from), format(b.to), b.count])}
      />
    </figure>
  );
}
