"use client";

import { CheckCircle2, CircleAlert, Loader2, MinusCircle } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/card";
import { SkeletonBlock } from "@/components/ui/states";
import { ApiUnreachableError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useHealth } from "./use-health";

type RowState = "ok" | "waking" | "down" | "not_configured" | "loading";

const ICON: Record<RowState, React.ReactNode> = {
  ok: <CheckCircle2 size={16} className="text-positive" aria-hidden="true" />,
  waking: <Loader2 size={16} className="animate-spin text-warning" aria-hidden="true" />,
  loading: <Loader2 size={16} className="animate-spin text-muted" aria-hidden="true" />,
  down: <CircleAlert size={16} className="text-negative" aria-hidden="true" />,
  not_configured: <MinusCircle size={16} className="text-subtle" aria-hidden="true" />,
};

function Row({ name, state, detail }: { name: string; state: RowState; detail: string }) {
  return (
    <li className="flex items-center justify-between gap-3 border-t border-border py-2.5 first:border-t-0">
      <span className="flex items-center gap-2">
        {ICON[state]}
        <span className="font-medium">{name}</span>
      </span>
      <span className="num text-right text-sm text-muted">{detail}</span>
    </li>
  );
}

export function SystemStatus() {
  const { data, error, isPending, failureCount, refetch, isFetching } = useHealth();

  const waking = isPending && failureCount > 0;
  const apiDown = !isPending && error;

  let api: { state: RowState; detail: string };
  if (data) api = { state: "ok", detail: `v${data.version} · ${data.environment}` };
  else if (waking) api = { state: "waking", detail: "Waking up the analytics server…" };
  else if (isPending) api = { state: "loading", detail: "Checking…" };
  else
    api = {
      state: "down",
      detail: error instanceof ApiUnreachableError ? "Not responding" : "Returned an error",
    };

  let db: { state: RowState; detail: string };
  if (!data)
    db = {
      state: apiDown ? "down" : isPending ? "loading" : "down",
      detail: apiDown ? "Unknown (API offline)" : "Checking…",
    };
  else if (data.database.status === "ok")
    db = { state: "ok", detail: `Connected · ${data.database.latency_ms ?? "?"} ms` };
  else if (data.database.status === "not_configured")
    db = { state: "not_configured", detail: "Not configured" };
  else db = { state: "down", detail: "Unavailable" };

  return (
    <Card>
      <CardHeader
        title="System status"
        subtitle="Each tier of the deployment, checked from your browser."
        action={
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted hover:text-text disabled:opacity-50"
          >
            Recheck
          </button>
        }
      />
      <ul aria-live="polite">
        <Row name="Web app" state="ok" detail="Serving this page" />
        <Row name="Analytics API" state={api.state} detail={api.detail} />
        <Row name="Database" state={db.state} detail={db.detail} />
      </ul>
      {waking ? (
        <p className="mt-3 text-sm text-muted">
          The API runs on a free tier that sleeps when idle. The first request after a quiet period
          can take up to a minute.
        </p>
      ) : null}
      <div className="mt-3 border-t border-border pt-2 text-xs text-subtle">
        {data ? (
          <>
            Server time {formatDate(data.server_time)} ·{" "}
            {new Date(data.server_time).toISOString().slice(11, 19)} UTC
          </>
        ) : isPending ? (
          <SkeletonBlock className="h-3 w-40" />
        ) : (
          <>Last check failed</>
        )}
      </div>
    </Card>
  );
}
