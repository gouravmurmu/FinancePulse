import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { useAuth } from "@/components/auth/auth-provider";
import { apiGet, apiSend, apiText, qs } from "./api";
import { FreshnessSchema, PointSchema, QuoteSchema } from "./market";

export const PortfolioSchema = z.object({
  id: z.string(),
  name: z.string(),
  base_currency: z.enum(["USD", "INR"]),
  benchmark_id: z.string().nullable(),
  transaction_count: z.number(),
  created_at: z.string(),
});
export type Portfolio = z.infer<typeof PortfolioSchema>;

export const UNITS = ["unit", "troy_oz", "gram"] as const;
export type Unit = (typeof UNITS)[number];

export const TransactionSchema = z.object({
  id: z.string(),
  instrument_id: z.string(),
  name: z.string(),
  side: z.enum(["buy", "sell"]),
  trade_date: z.string(),
  quantity: z.number(),
  unit: z.enum(UNITS),
  price: z.number(),
  fees: z.number(),
  currency: z.enum(["USD", "INR"]),
  notes: z.string().nullable(),
});
export type Transaction = z.infer<typeof TransactionSchema>;
export type TransactionInput = Omit<Transaction, "id" | "name" | "currency">;

const n = z.number().nullable();

const HoldingSchema = z.object({
  instrument_id: z.string(),
  name: z.string(),
  asset_class: z.string(),
  asset_class_label: z.string(),
  sector: z.string().nullable(),
  currency: z.enum(["USD", "INR"]),
  unit: z.enum(UNITS),
  quantity: z.number(),
  average_cost: n,
  price: n,
  cost_local: n,
  cost_base: n,
  value_local: n,
  value_base: n,
  unrealized_local: n,
  unrealized_base: n,
  unrealized_pct: n,
  price_effect_base: n,
  fx_effect_base: n,
  realized_base: n,
  fx_rate: n,
  weight: n,
  freshness: FreshnessSchema,
  price_definition: z.string().nullable(),
});
export type Holding = z.infer<typeof HoldingSchema>;

const SliceSchema = z.object({ label: z.string(), value: n, weight: n });
export type Slice = z.infer<typeof SliceSchema>;

export const SummarySchema = z.object({
  portfolio: PortfolioSchema,
  base_currency: z.enum(["USD", "INR"]),
  holdings: z.array(HoldingSchema),
  closed: z.array(
    z.object({
      instrument_id: z.string(),
      name: z.string(),
      realized_base: n,
      realized_local: n,
      currency: z.string(),
    }),
  ),
  totals: z
    .object({
      value: n,
      cost: n,
      unrealized: n,
      unrealized_pct: n,
      realized: n,
      total_pnl: n,
      price_effect: n,
      fx_effect: n,
      fees: n,
    })
    .nullable(),
  allocation: z.object({
    holding: z.array(SliceSchema),
    asset_class: z.array(SliceSchema),
    currency: z.array(SliceSchema),
    sector: z.array(SliceSchema),
  }),
  as_of: z.string().nullable(),
  notes: z.array(z.string()),
});
export type Summary = z.infer<typeof SummarySchema>;

export const PerformanceSchema = z.object({
  period: z.string(),
  base_currency: z.enum(["USD", "INR"]),
  start: z.string(),
  end: z.string(),
  observations: z.number(),
  periods_per_year: z.number(),
  portfolio: z.array(PointSchema),
  benchmark: z.object({
    instrument_id: z.string().nullable(),
    name: z.string().nullable(),
    points: z.array(PointSchema),
  }),
  value: z.array(PointSchema),
  drawdown: z.array(PointSchema),
  metrics: z.object({
    time_weighted_return: n,
    benchmark_return: n,
    volatility: n,
    sharpe: n,
    max_drawdown: n,
    var: n,
    beta: n,
  }),
  risk: z.array(
    z.object({
      instrument_id: z.string(),
      name: z.string(),
      weight: n,
      volatility: n,
      risk_contribution: n,
    }),
  ),
  correlation: z
    .object({
      ids: z.array(z.string()),
      names: z.array(z.string()),
      matrix: z.array(z.array(z.number())),
    })
    .nullable(),
  insight: z.string().nullable(),
  assumptions: z.array(z.string()),
  warning: z.string().nullable(),
});
export type Performance = z.infer<typeof PerformanceSchema>;

export const PortfolioStressSchema = z.object({
  weights: z.record(z.string(), z.number()),
  shocks: z.record(z.string(), z.number()),
  contributions: z.record(z.string(), z.number()),
  contribution_amounts: z.record(z.string(), n),
  total: z.number(),
  value: n,
  pnl: n,
  preset: z.string().nullable(),
  note: z.string(),
  base_currency: z.enum(["USD", "INR"]),
});
export type PortfolioStress = z.infer<typeof PortfolioStressSchema>;

export const ImportResultSchema = z.object({
  status: z.literal("ok"),
  rows: z.number(),
  dry_run: z.boolean(),
});

export const WatchlistSchema = z.object({
  id: z.string(),
  name: z.string(),
  instrument_ids: z.array(z.string()),
  quotes: z.array(QuoteSchema).optional(),
});
export type Watchlist = z.infer<typeof WatchlistSchema>;

const Nothing = z.null();

/** Calls that need the signed-in user's token. */
export function useAuthedApi() {
  const { getToken } = useAuth();
  return {
    async get<T>(path: string, schema: z.ZodType<T>) {
      return apiGet(path, schema, { token: await getToken(), timeoutMs: 45_000 });
    },
    async send<T>(
      method: "POST" | "PUT" | "PATCH" | "DELETE",
      path: string,
      body: unknown,
      schema: z.ZodType<T>,
    ) {
      return apiSend(method, path, body, schema, { token: await getToken(), timeoutMs: 45_000 });
    },
    async text(path: string) {
      return apiText(path, { token: await getToken(), timeoutMs: 45_000 });
    },
  };
}

/** Query keys for private data all start with "me" so sign-out clears them. */
export const keys = {
  portfolios: ["me", "portfolios"] as const,
  portfolio: (id: string) => ["me", "portfolio", id] as const,
  summary: (id: string) => ["me", "portfolio", id, "summary"] as const,
  transactions: (id: string) => ["me", "portfolio", id, "transactions"] as const,
  performance: (id: string, period: string) =>
    ["me", "portfolio", id, "performance", period] as const,
  watchlists: ["me", "watchlists"] as const,
  watchlist: (id: string, currency?: string) => ["me", "watchlist", id, currency ?? ""] as const,
};

export function usePortfolios() {
  const { session } = useAuth();
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.portfolios,
    queryFn: () => api.get("/api/v1/portfolios", z.array(PortfolioSchema)),
    enabled: !!session,
  });
}

export function useSummary(id: string | null) {
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.summary(id ?? ""),
    queryFn: () => api.get(`/api/v1/portfolios/${id}/summary`, SummarySchema),
    enabled: !!id,
  });
}

export function useTransactions(id: string | null) {
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.transactions(id ?? ""),
    queryFn: () => api.get(`/api/v1/portfolios/${id}/transactions`, z.array(TransactionSchema)),
    enabled: !!id,
  });
}

export function usePerformance(id: string | null, period: string, enabled: boolean) {
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.performance(id ?? "", period),
    queryFn: () =>
      api.get(`/api/v1/portfolios/${id}/performance${qs({ period })}`, PerformanceSchema),
    enabled: !!id && enabled,
    retry: false,
  });
}

/** Invalidate everything derived from one portfolio's ledger. */
export function useInvalidatePortfolio() {
  const qc = useQueryClient();
  return (id: string) => {
    void qc.invalidateQueries({ queryKey: keys.portfolio(id) });
    void qc.invalidateQueries({ queryKey: keys.portfolios });
  };
}

export function usePortfolioMutations() {
  const api = useAuthedApi();
  const qc = useQueryClient();
  const invalidate = useInvalidatePortfolio();
  return {
    create: useMutation({
      mutationFn: (body: { name: string; base_currency: "USD" | "INR"; benchmark_id?: string }) =>
        api.send("POST", "/api/v1/portfolios", body, PortfolioSchema),
      onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolios }),
    }),
    update: useMutation({
      mutationFn: ({ id, ...body }: { id: string; name?: string; benchmark_id?: string }) =>
        api.send("PATCH", `/api/v1/portfolios/${id}`, body, PortfolioSchema),
      onSuccess: (p) => invalidate(p.id),
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        api.send("DELETE", `/api/v1/portfolios/${id}`, undefined, Nothing),
      onSuccess: () => qc.invalidateQueries({ queryKey: keys.portfolios }),
    }),
    addTx: useMutation({
      mutationFn: ({ pid, tx }: { pid: string; tx: TransactionInput }) =>
        api.send("POST", `/api/v1/portfolios/${pid}/transactions`, tx, TransactionSchema),
      onSuccess: (_, v) => invalidate(v.pid),
    }),
    updateTx: useMutation({
      mutationFn: ({ pid, id, tx }: { pid: string; id: string; tx: TransactionInput }) =>
        api.send("PUT", `/api/v1/portfolios/${pid}/transactions/${id}`, tx, TransactionSchema),
      onSuccess: (_, v) => invalidate(v.pid),
    }),
    deleteTx: useMutation({
      mutationFn: ({ pid, id }: { pid: string; id: string }) =>
        api.send("DELETE", `/api/v1/portfolios/${pid}/transactions/${id}`, undefined, Nothing),
      onSuccess: (_, v) => invalidate(v.pid),
    }),
    importCsv: useMutation({
      mutationFn: ({ pid, csv, dryRun }: { pid: string; csv: string; dryRun: boolean }) =>
        api.send(
          "POST",
          `/api/v1/portfolios/${pid}/import`,
          { csv, dry_run: dryRun },
          ImportResultSchema,
        ),
      onSuccess: (r, v) => {
        if (!r.dry_run) invalidate(v.pid);
      },
    }),
    stress: useMutation({
      mutationFn: ({
        pid,
        preset,
        shocks,
      }: {
        pid: string;
        preset?: string;
        shocks?: Record<string, number>;
      }) =>
        api.send(
          "POST",
          `/api/v1/portfolios/${pid}/stress`,
          { preset, shocks },
          PortfolioStressSchema,
        ),
    }),
    exportCsv: (pid: string) => api.text(`/api/v1/portfolios/${pid}/transactions.csv`),
  };
}

export function useWatchlists() {
  const { session } = useAuth();
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.watchlists,
    queryFn: () => api.get("/api/v1/watchlists", z.array(WatchlistSchema)),
    enabled: !!session,
  });
}

export function useWatchlist(id: string | null, currency?: "USD" | "INR") {
  const api = useAuthedApi();
  return useQuery({
    queryKey: keys.watchlist(id ?? "", currency),
    queryFn: () =>
      api.get(`/api/v1/watchlists/${id}${qs({ period: "1D", currency })}`, WatchlistSchema),
    enabled: !!id,
  });
}

export function useWatchlistMutations() {
  const api = useAuthedApi();
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: keys.watchlists });
    void qc.invalidateQueries({ queryKey: ["me", "watchlist"] });
  };
  return {
    create: useMutation({
      mutationFn: (name: string) =>
        api.send("POST", "/api/v1/watchlists", { name }, WatchlistSchema),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        api.send("DELETE", `/api/v1/watchlists/${id}`, undefined, Nothing),
      onSuccess: refresh,
    }),
    addItem: useMutation({
      mutationFn: ({ id, instrumentId }: { id: string; instrumentId: string }) =>
        api.send(
          "POST",
          `/api/v1/watchlists/${id}/items`,
          { instrument_id: instrumentId },
          WatchlistSchema,
        ),
      onSuccess: refresh,
    }),
    removeItem: useMutation({
      mutationFn: ({ id, instrumentId }: { id: string; instrumentId: string }) =>
        api.send(
          "DELETE",
          `/api/v1/watchlists/${id}/items/${encodeURIComponent(instrumentId)}`,
          undefined,
          Nothing,
        ),
      onSuccess: refresh,
    }),
  };
}
