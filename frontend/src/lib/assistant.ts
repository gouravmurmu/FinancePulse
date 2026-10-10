import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet } from "./api";
import { useAuthedApi } from "./portfolio";

export const AssistantStatusSchema = z.object({
  configured: z.boolean(),
  model: z.string().nullable(),
  limits: z.object({ requests_per_day: z.number(), tokens_per_day: z.number() }),
});

export const AnswerSchema = z.object({
  answer: z.string(),
  tool_calls: z.array(
    z.object({ tool: z.string(), arguments: z.record(z.string(), z.unknown()), ok: z.boolean() }),
  ),
  sources: z.array(z.string()),
  model: z.string(),
  usage: z.object({
    tokens: z.number(),
    requests_today: z.number(),
    requests_left: z.number(),
    tokens_today: z.number(),
  }),
  disclaimer: z.string(),
});
export type Answer = z.infer<typeof AnswerSchema>;

export type ChatTurn =
  { role: "user"; content: string } | { role: "assistant"; content: string; meta?: Answer };

export type AssistantContext = { instrument_id?: string; portfolio_id?: string };

export const TOOL_LABEL: Record<string, string> = {
  search_instruments: "Searched instruments",
  get_quote: "Latest price",
  get_risk: "Return and risk metrics",
  compare_assets: "Compared assets",
  get_fundamentals: "SEC financials",
  get_news: "Headlines",
  get_forecast: "Forecast check",
  get_anomalies: "Unusual activity",
  get_portfolio: "Your portfolio",
  stress_portfolio: "Stress test",
};

export function useAssistantStatus() {
  return useQuery({
    queryKey: ["assistant", "status"],
    queryFn: () => apiGet("/api/v1/assistant/status", AssistantStatusSchema),
    staleTime: 10 * 60_000,
  });
}

export function useAsk() {
  const api = useAuthedApi();
  return useMutation({
    mutationFn: ({ turns, context }: { turns: ChatTurn[]; context: AssistantContext }) =>
      api.send(
        "POST",
        "/api/v1/assistant/chat",
        {
          messages: turns.slice(-8).map((t) => ({ role: t.role, content: t.content })),
          context,
        },
        AnswerSchema,
      ),
  });
}
