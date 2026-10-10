"use client";

import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type SeriesType,
} from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";
import { abbreviate } from "@/lib/format";
import type { Bar, Point } from "@/lib/market";

export type Overlay = { id: string; label: string; color: string; points: Point[] };

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Price chart (TradingView Lightweight Charts, Apache-2.0 with attribution).
 * Canvas cannot read CSS variables, so token values are resolved per theme.
 */
export function PriceChart({
  bars,
  mode,
  showVolume,
  overlays = [],
  format,
  caption,
  height = 360,
}: {
  bars: Bar[];
  mode: "line" | "candle";
  showVolume: boolean;
  overlays?: Overlay[];
  format: (v: number) => string;
  caption: string;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const text = token("--text-muted");
    const grid = token("--chart-grid");
    const chart: IChartApi = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: text,
        fontFamily: getComputedStyle(document.body).fontFamily,
        fontSize: 12,
        // Attribution is the visible "Charts by TradingView" link under the chart.
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
    });

    const priced = bars.filter((b) => b.close !== null);
    const priceFormat = { type: "custom" as const, formatter: format, minMove: 0.0001 };
    let main: ISeriesApi<SeriesType>;
    if (mode === "candle") {
      main = chart.addSeries(CandlestickSeries, {
        upColor: token("--positive"),
        downColor: token("--negative"),
        borderVisible: false,
        wickUpColor: token("--positive"),
        wickDownColor: token("--negative"),
        priceFormat,
      });
      main.setData(
        priced
          .filter((b) => b.open !== null && b.high !== null && b.low !== null)
          .map((b) => ({
            time: b.date,
            open: b.open!,
            high: b.high!,
            low: b.low!,
            close: b.close!,
          })),
      );
    } else {
      main = chart.addSeries(LineSeries, { color: token("--chart-1"), lineWidth: 2, priceFormat });
      main.setData(priced.map((b) => ({ time: b.date, value: b.close! })));
    }

    for (const o of overlays) {
      const color = o.color.startsWith("var(") ? token(o.color.slice(4, -1)) : o.color;
      const s = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        title: o.label,
        priceFormat,
      });
      s.setData(o.points.map((p) => ({ time: p.date, value: p.value })));
    }

    if (showVolume && priced.some((b) => (b.volume ?? 0) > 0)) {
      const vol = chart.addSeries(
        HistogramSeries,
        {
          color: token("--text-subtle"),
          priceFormat: { type: "custom", formatter: (v: number) => abbreviate(v), minMove: 1 },
          priceLineVisible: false,
        },
        1,
      );
      vol.setData(priced.map((b) => ({ time: b.date, value: b.volume ?? 0 })));
      chart.panes()[1]?.setHeight(Math.round(height * 0.22));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, mode, showVolume, overlays, format, height, resolvedTheme]);

  return (
    <figure>
      {/* The canvas library builds layout tables; the table view below is the accessible version. */}
      <p className="sr-only">{caption}</p>
      <div ref={ref} style={{ height }} aria-hidden="true" />
      <figcaption className="mt-1 text-xs text-subtle">
        Charts by{" "}
        <a
          href="https://www.tradingview.com/"
          target="_blank"
          rel="noreferrer"
          className="underline hover:text-text"
        >
          TradingView
        </a>
      </figcaption>
    </figure>
  );
}
