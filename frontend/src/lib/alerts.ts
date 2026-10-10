import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { useAuth } from "@/components/auth/auth-provider";
import { apiGet, qs } from "./api";
import { marketApi, type Instrument } from "./market";
import { useAuthedApi } from "./portfolio";

export const ANOMALY_KINDS = ["return", "volume", "volatility", "correlation"] as const;

export const AnomalySchema = z.object({
  instrument_id: z.string(),
  observed_at: z.string(),
  kind: z.enum(ANOMALY_KINDS),
  label: z.string(),
  description: z.string(),
  value: z.number(),
  baseline: z.number().nullable(),
  zscore: z.number(),
  threshold: z.number(),
});
export type Anomaly = z.infer<typeof AnomalySchema>;

export const RULE_KINDS = [
  "price_above",
  "price_below",
  "move_pct",
  "volatility_above",
  "anomaly",
] as const;
export type RuleKind = (typeof RULE_KINDS)[number];

export const RULE_KIND_LABEL: Record<RuleKind, string> = {
  price_above: "Price rises above",
  price_below: "Price falls below",
  move_pct: "Daily move of at least",
  volatility_above: "20-day volatility above",
  anomaly: "Any statistical anomaly",
};

/** Move and volatility thresholds are entered as percentages, prices as prices. */
export function isPercentRule(kind: RuleKind): boolean {
  return kind === "move_pct" || kind === "volatility_above";
}

export const RuleSchema = z.object({
  id: z.string(),
  instrument_id: z.string(),
  instrument_name: z.string(),
  currency: z.string().nullable(),
  kind: z.enum(RULE_KINDS),
  label: z.string(),
  threshold: z.number().nullable(),
  active: z.boolean(),
  condition_met: z.boolean().nullable(),
  last_evaluated_on: z.string().nullable(),
  created_at: z.string(),
});
export type Rule = z.infer<typeof RuleSchema>;

export const EventSchema = z.object({
  id: z.string(),
  rule_id: z.string(),
  instrument_id: z.string(),
  observed_at: z.string(),
  message: z.string(),
  details: z.record(z.string(), z.unknown()),
  read: z.boolean(),
  created_at: z.string(),
});
export type AlertEvent = z.infer<typeof EventSchema>;

const EventsSchema = z.object({ events: z.array(EventSchema), unread: z.number() });

export const alertKeys = {
  rules: ["me", "alerts", "rules"] as const,
  events: ["me", "alerts", "events"] as const,
};

export function useAnomalies(instrumentId: string | null, days: number) {
  return useQuery({
    queryKey: ["anomalies", instrumentId ?? "all", days],
    queryFn: () =>
      apiGet(
        `/api/v1/anomalies${qs({ instrument_id: instrumentId ?? undefined, days, limit: 100 })}`,
        z.array(AnomalySchema),
        { timeoutMs: 45_000 },
      ),
  });
}

export function useAlertRules() {
  const { session } = useAuth();
  const api = useAuthedApi();
  return useQuery({
    queryKey: alertKeys.rules,
    queryFn: () => api.get("/api/v1/alerts/rules", z.array(RuleSchema)),
    enabled: !!session,
  });
}

export function useAlertEvents() {
  const { session } = useAuth();
  const api = useAuthedApi();
  return useQuery({
    queryKey: alertKeys.events,
    queryFn: () => api.get("/api/v1/alerts/events", EventsSchema),
    enabled: !!session,
    // Alerts are evaluated twice a day, so there is no point polling often.
    staleTime: 5 * 60_000,
  });
}

export function useAlertMutations() {
  const api = useAuthedApi();
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: ["me", "alerts"] });
  return {
    create: useMutation({
      mutationFn: (body: { instrument_id: string; kind: RuleKind; threshold: number | null }) =>
        api.send("POST", "/api/v1/alerts/rules", body, RuleSchema),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, ...body }: { id: string; active?: boolean; threshold?: number }) =>
        api.send("PATCH", `/api/v1/alerts/rules/${id}`, body, RuleSchema),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        api.send("DELETE", `/api/v1/alerts/rules/${id}`, undefined, z.null()),
      onSuccess: refresh,
    }),
    markRead: useMutation({
      mutationFn: (ids?: string[]) =>
        api.send(
          "POST",
          "/api/v1/alerts/events/read",
          ids ? { ids } : {},
          z.object({ updated: z.number() }),
        ),
      onSuccess: refresh,
    }),
  };
}

/** All tracked instruments by id, for labelling anomaly rows and prefilled forms. */
export function useInstrumentIndex() {
  return useQuery({
    queryKey: ["instruments", "all"],
    queryFn: () => marketApi.instruments(),
    staleTime: 60 * 60_000,
    select: (list) => Object.fromEntries(list.map((i) => [i.id, i])) as Record<string, Instrument>,
  });
}
