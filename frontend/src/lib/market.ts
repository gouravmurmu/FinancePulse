import { z } from "zod";
import { apiGet, apiPost, qs } from "./api";
import type { Freshness as ChipFreshness } from "@/components/ui/freshness-chip";

/** Schemas mirror backend/app/schemas/market.py. */

export const PERIODS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX"] as const;
export type Period = (typeof PERIODS)[number];
export type Region = "global" | "india";
export type DisplayCurrency = "USD" | "INR";

const FreshnessSchema = z.object({
  kind: z.enum(["live", "delayed", "eod", "stale", "unavailable", "demo"]),
  as_of: z.string().nullable().optional(),
});
export type ApiFreshness = z.infer<typeof FreshnessSchema>;

/** Map the API freshness to the chip's props. */
export function toChip(f: ApiFreshness): ChipFreshness {
  switch (f.kind) {
    case "eod":
    case "stale":
      return f.as_of ? { kind: f.kind, asOf: f.as_of } : { kind: "unavailable" };
    case "delayed":
      // Daily bars for today's session; the exact delay is the provider's (about 15 min).
      return { kind: "delayed", minutes: 15 };
    default:
      return { kind: f.kind };
  }
}

export const InstrumentSchema = z.object({
  id: z.string(),
  name: z.string(),
  asset_class: z.string(),
  exchange: z.string().nullable(),
  country: z.string().nullable(),
  currency: z.string(),
  timezone: z.string(),
  price_definition: z.string().nullable(),
  region: z.string(),
  sector: z.string().nullable().optional(),
  benchmark_id: z.string().nullable().optional(),
});
export type Instrument = z.infer<typeof InstrumentSchema>;

export const QuoteSchema = z.object({
  instrument_id: z.string(),
  name: z.string(),
  asset_class: z.string(),
  region: z.string(),
  price: z.number().nullable(),
  change: z.number().nullable(),
  change_pct: z.number().nullable(),
  currency: z.string(),
  converted: z.boolean(),
  as_of: z.string().nullable(),
  freshness: FreshnessSchema,
  sparkline: z.array(z.number()),
  sector: z.string().nullable().optional(),
});
export type Quote = z.infer<typeof QuoteSchema>;

const PointSchema = z.object({ date: z.string(), value: z.number() });
export type Point = z.infer<typeof PointSchema>;

export const ComparisonSchema = z.object({
  period: z.string(),
  start: z.string().nullable(),
  series: z.array(z.object({ instrument_id: z.string(), points: z.array(PointSchema) })),
  notes: z.array(z.string()),
});
export type Comparison = z.infer<typeof ComparisonSchema>;

export const OverviewSchema = z.object({
  region: z.string(),
  currency: z.string(),
  period: z.string(),
  indices: z.array(QuoteSchema),
  snapshots: z.array(QuoteSchema),
  gainers: z.array(QuoteSchema),
  losers: z.array(QuoteSchema),
  heatmap: z.array(QuoteSchema),
  comparison: ComparisonSchema,
  markets: z.array(
    z.object({ session: z.string(), name: z.string(), timezone: z.string(), open: z.boolean() }),
  ),
  data_status: z
    .object({
      status: z.string(),
      started_at: z.string(),
      finished_at: z.string().nullable(),
      last_success_at: z.string().nullable(),
      failed: z.array(z.string()),
    })
    .nullable(),
  refresh_schedule: z.string(),
});
export type Overview = z.infer<typeof OverviewSchema>;

const BarSchema = z.object({
  date: z.string(),
  open: z.number().nullable(),
  high: z.number().nullable(),
  low: z.number().nullable(),
  close: z.number().nullable(),
  volume: z.number().nullable(),
  quote_type: z.string(),
  quality: z.string(),
});
export type Bar = z.infer<typeof BarSchema>;

export const HistorySchema = z.object({
  instrument_id: z.string(),
  currency: z.string(),
  converted: z.boolean(),
  provider: z.string().nullable().optional(),
  retrieved_at: z.string().nullable().optional(),
  bars: z.array(BarSchema),
  source_note: z.string(),
});
export type History = z.infer<typeof HistorySchema>;

export const DetailSchema = z.object({
  instrument: InstrumentSchema,
  quote: QuoteSchema,
  market_open: z.boolean().nullable(),
  snapshot: z
    .object({
      provider: z.string(),
      as_of: z.string(),
      market_cap: z.number().nullable(),
      circulating_supply: z.number().nullable(),
      total_supply: z.number().nullable(),
      max_supply: z.number().nullable(),
      volume_24h: z.number().nullable(),
      source_note: z.string(),
    })
    .nullable(),
  related: z.array(InstrumentSchema),
  metal_context: z
    .object({
      gold_silver_ratio: z.number().nullable(),
      gold_silver_ratio_series: z.array(PointSchema),
      inr_decomposition: z
        .object({
          usd_return: z.number(),
          fx_return: z.number(),
          inr_return: z.number(),
          explanation: z.string(),
        })
        .nullable(),
    })
    .nullable()
    .optional(),
});
export type Detail = z.infer<typeof DetailSchema>;

export const IndicatorsSchema = z.object({
  instrument_id: z.string(),
  currency: z.string().nullable().optional(),
  series: z.record(z.string(), z.array(PointSchema)),
});
export type Indicators = z.infer<typeof IndicatorsSchema>;

export const InstrumentRiskSchema = z.object({
  instrument_id: z.string(),
  period: z.string(),
  observations: z.number(),
  periods_per_year: z.number(),
  confidence: z.number(),
  benchmark_id: z.string().nullable(),
  metrics: z.object({
    total_return: z.number().nullable(),
    cagr: z.number().nullable(),
    volatility: z.number().nullable(),
    sharpe: z.number().nullable(),
    sortino: z.number().nullable(),
    max_drawdown: z.number().nullable(),
    max_drawdown_peak: z.string().nullable(),
    max_drawdown_trough: z.string().nullable(),
    max_drawdown_recovery: z.string().nullable(),
    var: z.number().nullable(),
    expected_shortfall: z.number().nullable(),
    beta: z.number().nullable(),
  }),
  risk_level: z.enum(["low", "moderate", "high"]).nullable(),
  drawdown: z.array(PointSchema),
  rolling_volatility: z.array(PointSchema),
  assumptions: z.array(z.string()),
  insight: z.string().nullable(),
  warning: z.string().nullable().optional(),
});
export type InstrumentRisk = z.infer<typeof InstrumentRiskSchema>;

const RiskRowSchema = z.object({
  instrument_id: z.string(),
  name: z.string(),
  total_return: z.number().nullable(),
  volatility: z.number().nullable(),
  sharpe: z.number().nullable(),
  sortino: z.number().nullable(),
  max_drawdown: z.number().nullable(),
  var: z.number().nullable(),
  expected_shortfall: z.number().nullable(),
  risk_level: z.enum(["low", "moderate", "high"]).nullable(),
});
export type RiskRow = z.infer<typeof RiskRowSchema>;

export const RiskLabSchema = z.object({
  period: z.string(),
  start: z.string(),
  end: z.string(),
  observations: z.number(),
  periods_per_year: z.number(),
  confidence: z.number(),
  window: z.number(),
  metrics: z.array(RiskRowSchema),
  correlation: z.object({ ids: z.array(z.string()), matrix: z.array(z.array(z.number())) }),
  rolling_correlation: z.object({ pair: z.array(z.string()), points: z.array(PointSchema) }),
  drawdowns: z.record(z.string(), z.array(PointSchema)),
  insight: z.string().nullable(),
  assumptions: z.array(z.string()),
});
export type RiskLab = z.infer<typeof RiskLabSchema>;

export const MonteCarloSchema = z.object({
  weights: z.record(z.string(), z.number()),
  initial_value: z.number(),
  horizon_days: z.number(),
  paths: z.number(),
  seed: z.number(),
  lookback: z.string(),
  periods_per_year: z.number(),
  estimation_window: z.object({ start: z.string(), end: z.string(), observations: z.number() }),
  percentiles: z.record(z.string(), z.array(z.number())),
  final: z.object({ p5: z.number(), p50: z.number(), p95: z.number(), mean: z.number() }),
  probability_of_loss: z.number(),
  histogram: z.array(z.object({ from: z.number(), to: z.number(), count: z.number() })),
  assumptions: z.array(z.string()),
});
export type MonteCarlo = z.infer<typeof MonteCarloSchema>;

export const StressSchema = z.object({
  weights: z.record(z.string(), z.number()),
  shocks: z.record(z.string(), z.number()),
  contributions: z.record(z.string(), z.number()),
  total: z.number(),
  preset: z.string().nullable(),
  note: z.string(),
});
export type Stress = z.infer<typeof StressSchema>;

export const StressPresetsSchema = z.array(
  z.object({ id: z.string(), label: z.string(), description: z.string() }),
);

const n = z.number().nullable();
export const FundamentalsSchema = z.object({
  instrument_id: z.string(),
  available: z.boolean(),
  reason: z.string().nullable(),
  currency: z.string(),
  source: z.string(),
  last_filed: z.string().nullable(),
  retrieved_at: z.string().nullable(),
  years: z.array(
    z.object({
      fiscal_year: z.number(),
      period_end: z.string(),
      revenue: n,
      gross_profit: n,
      operating_income: n,
      net_income: n,
      eps_diluted: n,
      operating_cash_flow: n,
      capex: n,
      total_assets: n,
      total_liabilities: n,
      equity: n,
      long_term_debt: n,
      cash: n,
      gross_margin: n,
      operating_margin: n,
      net_margin: n,
      free_cash_flow: n,
      debt_to_equity: n,
      revenue_growth: n,
      net_income_growth: n,
    }),
  ),
});
export type Fundamentals = z.infer<typeof FundamentalsSchema>;

const enc = encodeURIComponent;

/** Market data and analytics endpoints can be slow while Render wakes up. */
const SLOW = { timeoutMs: 45_000 };

export const marketApi = {
  overview: (region: Region, currency: DisplayCurrency, period: Period) =>
    apiGet(`/api/v1/markets/overview${qs({ region, currency, period })}`, OverviewSchema, SLOW),
  search: (q: string, limit = 12) =>
    apiGet(`/api/v1/instruments${qs({ q, limit })}`, z.array(InstrumentSchema)),
  instruments: () => apiGet(`/api/v1/instruments${qs({ limit: 100 })}`, z.array(InstrumentSchema)),
  detail: (id: string, period: Period, currency?: DisplayCurrency) =>
    apiGet(`/api/v1/instruments/${enc(id)}${qs({ period, currency })}`, DetailSchema, SLOW),
  history: (id: string, period: Period, currency?: DisplayCurrency) =>
    apiGet(
      `/api/v1/instruments/${enc(id)}/history${qs({ period, currency })}`,
      HistorySchema,
      SLOW,
    ),
  indicators: (id: string, period: Period, currency?: DisplayCurrency) =>
    apiGet(
      `/api/v1/instruments/${enc(id)}/indicators${qs({ period, currency })}`,
      IndicatorsSchema,
      SLOW,
    ),
  fundamentals: (id: string) =>
    apiGet(`/api/v1/instruments/${enc(id)}/fundamentals`, FundamentalsSchema, SLOW),
  risk: (id: string, period: Period) =>
    apiGet(`/api/v1/instruments/${enc(id)}/risk${qs({ period })}`, InstrumentRiskSchema, SLOW),
  riskLab: (body: {
    instrument_ids: string[];
    period: Period;
    confidence?: number;
    window?: number;
  }) => apiPost(`/api/v1/risk/analyze`, body, RiskLabSchema, SLOW),
  monteCarlo: (body: {
    weights: Record<string, number>;
    initial_value: number;
    horizon_days: number;
    paths: number;
    seed: number;
    lookback: Period;
  }) => apiPost(`/api/v1/risk/monte-carlo`, body, MonteCarloSchema, SLOW),
  stress: (body: {
    weights: Record<string, number>;
    preset?: string;
    shocks?: Record<string, number>;
  }) => apiPost(`/api/v1/risk/stress`, body, StressSchema, SLOW),
  stressPresets: () => apiGet(`/api/v1/risk/stress-presets`, StressPresetsSchema),
};

export const ASSET_CLASS_LABEL: Record<string, string> = {
  index: "Index",
  equity: "Stock",
  crypto: "Crypto",
  commodity: "Metal",
  etf: "ETF",
  fx: "Currency",
};

export function assetHref(id: string): string {
  return `/assets/${encodeURIComponent(id)}`;
}
