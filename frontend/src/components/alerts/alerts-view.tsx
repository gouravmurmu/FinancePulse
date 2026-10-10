"use client";

import Link from "next/link";
import { Bell, BellOff, CheckCheck, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { buttonClass, errorMessage, inputClass, primaryClass } from "@/components/portfolio/forms";
import { InstrumentPicker } from "@/components/risk/instrument-picker";
import { Card, CardHeader } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { QueryState } from "@/components/ui/query-state";
import { EmptyState, SkeletonCard } from "@/components/ui/states";
import {
  RULE_KINDS,
  RULE_KIND_LABEL,
  isPercentRule,
  useAlertEvents,
  useAlertMutations,
  useAlertRules,
  useAnomalies,
  useInstrumentIndex,
  type Rule,
  type RuleKind,
} from "@/lib/alerts";
import { cn } from "@/lib/cn";
import { formatDate, formatPercent, formatPrice } from "@/lib/format";
import { assetHref } from "@/lib/market";
import { AnomalyList } from "./anomaly-list";

export const SCHEDULE_NOTE =
  "Checked twice a day, after the 11:00 and 22:30 UTC data refresh, on end-of-day closes. Alerts are not real-time and appear here in the app.";

export function AlertsView() {
  const { ready, configured, session } = useAuth();
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">Alerts</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{SCHEDULE_NOTE}</p>
      </header>
      <div className="grid gap-6 xl:grid-cols-12 [&>*]:min-w-0">
        <div className="flex flex-col gap-6 xl:col-span-7">
          {!ready ? (
            <SkeletonCard lines={4} />
          ) : !configured ? (
            <EmptyState
              icon={<Bell size={28} />}
              title="Alerts need sign-in"
              description="This deployment has no sign-in configured, so personal alerts are switched off. The anomaly feed still works."
            />
          ) : !session ? (
            <EmptyState
              icon={<Bell size={28} />}
              title="Set alerts on prices, big moves and unusual activity"
              description="Sign in to create alerts. They are checked on a schedule and shown here; your alerts are visible only to you."
              action={
                <Link href="/sign-in?next=/alerts" className={primaryClass}>
                  Sign in or create an account
                </Link>
              }
            />
          ) : (
            <>
              <Inbox />
              <Rules />
            </>
          )}
        </div>
        <div className="xl:col-span-5">
          <RecentAnomalies />
        </div>
      </div>
    </div>
  );
}

function Inbox() {
  const events = useAlertEvents();
  const m = useAlertMutations();
  return (
    <Card>
      <CardHeader
        title="Triggered"
        subtitle={
          events.data
            ? events.data.unread
              ? `${events.data.unread} unread`
              : "All caught up"
            : undefined
        }
        action={
          events.data?.unread ? (
            <button
              type="button"
              className={buttonClass}
              disabled={m.markRead.isPending}
              onClick={() => m.markRead.mutate(undefined)}
            >
              <CheckCheck size={15} aria-hidden="true" /> Mark all read
            </button>
          ) : null
        }
      />
      <QueryState query={events} skeletonLines={3}>
        {(d) =>
          d.events.length === 0 ? (
            <p className="text-sm text-muted">
              Nothing has triggered yet. When an alert fires it shows up here after the next
              scheduled check.
            </p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {d.events.map((e) => (
                <li key={e.id} className="flex items-start gap-3 py-2.5">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mt-1.5 size-2 shrink-0 rounded-full",
                      e.read ? "bg-transparent" : "bg-accent",
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <p className={cn("text-sm", !e.read && "font-medium")}>
                      {e.read ? null : <span className="sr-only">Unread: </span>}
                      {e.message}
                    </p>
                    <p className="text-xs text-subtle">
                      Close of {formatDate(e.observed_at)} ·{" "}
                      <Link href={assetHref(e.instrument_id)} className="hover:text-text">
                        Open asset
                      </Link>
                    </p>
                  </div>
                  {e.read ? null : (
                    <button
                      type="button"
                      className="text-xs text-muted hover:text-text"
                      onClick={() => m.markRead.mutate([e.id])}
                    >
                      Mark read
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )
        }
      </QueryState>
    </Card>
  );
}

function thresholdText(r: Rule): string {
  if (r.threshold === null) return "";
  if (isPercentRule(r.kind)) return formatPercent(r.threshold, { signed: false });
  return formatPrice(r.threshold, r.currency ?? "USD");
}

function Rules() {
  const rules = useAlertRules();
  const m = useAlertMutations();
  const [adding, setAdding] = useState(false);
  const [prefill, setPrefill] = useState<string | null>(null);

  useEffect(() => {
    // "Alert me" on an asset page links here with ?instrument=<id>.
    const id = new URLSearchParams(window.location.search).get("instrument");
    if (id) {
      setPrefill(id);
      setAdding(true);
    }
  }, []);

  return (
    <Card>
      <CardHeader
        title="Your alerts"
        subtitle={rules.data ? `${rules.data.length} of 50` : undefined}
        action={
          adding ? null : (
            <button type="button" className={primaryClass} onClick={() => setAdding(true)}>
              <Plus size={15} aria-hidden="true" /> New alert
            </button>
          )
        }
      />
      {adding ? (
        <NewRuleForm
          prefill={prefill}
          onDone={() => {
            // The prefilled asset applies to the first form only.
            setPrefill(null);
            setAdding(false);
          }}
        />
      ) : null}
      <QueryState query={rules} skeletonLines={3}>
        {(list) =>
          list.length === 0 ? (
            adding ? null : (
              <p className="text-sm text-muted">
                No alerts yet. Create one for a price level, a large daily move, high volatility or
                any statistical anomaly.
              </p>
            )
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {list.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className={cn("text-sm", !r.active && "text-muted")}>
                      <Link
                        href={assetHref(r.instrument_id)}
                        className="font-medium hover:underline"
                      >
                        {r.instrument_name}
                      </Link>{" "}
                      · {r.label} {thresholdText(r)}
                    </p>
                    <p className="text-xs text-subtle">
                      {!r.active
                        ? "Paused"
                        : r.last_evaluated_on
                          ? `Last checked on the ${formatDate(r.last_evaluated_on)} close${
                              r.kind !== "anomaly" && r.kind !== "move_pct" && r.condition_met
                                ? " · condition currently met"
                                : ""
                            }`
                          : "Waiting for the next scheduled check"}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={buttonClass}
                    onClick={() => m.update.mutate({ id: r.id, active: !r.active })}
                    aria-label={
                      r.active
                        ? `Pause alert on ${r.instrument_name}`
                        : `Resume alert on ${r.instrument_name}`
                    }
                  >
                    {r.active ? (
                      <>
                        <BellOff size={15} aria-hidden="true" /> Pause
                      </>
                    ) : (
                      <>
                        <Bell size={15} aria-hidden="true" /> Resume
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    className={buttonClass}
                    onClick={() => m.remove.mutate(r.id)}
                    aria-label={`Delete alert on ${r.instrument_name}`}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </QueryState>
      {m.update.error || m.remove.error ? (
        <p role="alert" className="mt-2 text-sm text-negative">
          {errorMessage(m.update.error ?? m.remove.error)}
        </p>
      ) : null}
    </Card>
  );
}

function NewRuleForm({ prefill, onDone }: { prefill: string | null; onDone: () => void }) {
  const m = useAlertMutations();
  const [instrument, setInstrument] = useState<{
    id: string;
    name: string;
    currency: string;
  } | null>(null);
  const [kind, setKind] = useState<RuleKind>("price_above");
  const [value, setValue] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const index = useInstrumentIndex();
  useEffect(() => {
    const known = prefill ? index.data?.[prefill] : undefined;
    if (known && !instrument) {
      setInstrument({ id: known.id, name: known.name, currency: known.currency });
    }
  }, [prefill, index.data, instrument]);

  const pct = isPercentRule(kind);
  const needsValue = kind !== "anomaly";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (!instrument) return setLocalError("Choose an asset.");
    let threshold: number | null = null;
    if (needsValue) {
      const n = Number(value);
      if (!value.trim() || !Number.isFinite(n) || n <= 0) {
        return setLocalError("Enter a number above zero.");
      }
      threshold = pct ? n / 100 : n;
    }
    m.create.mutate(
      { instrument_id: instrument.id, kind, threshold },
      {
        onSuccess: () => {
          if (prefill) window.history.replaceState(null, "", "/alerts");
          onDone();
        },
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      className="mb-4 flex flex-col gap-3 rounded-lg border border-border bg-bg p-3"
      aria-label="New alert"
    >
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Asset</span>
        <InstrumentPicker
          selected={instrument ? [instrument.id] : []}
          slots={{}}
          names={instrument ? { [instrument.id]: instrument.name } : {}}
          onAdd={(i) => setInstrument({ id: i.id, name: i.name, currency: i.currency })}
          onRemove={() => setInstrument(null)}
          max={1}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 [&>*]:min-w-0">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Condition</span>
          <select
            className={inputClass}
            value={kind}
            onChange={(e) => setKind(e.target.value as RuleKind)}
          >
            {RULE_KINDS.map((k) => (
              <option key={k} value={k}>
                {RULE_KIND_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        {needsValue ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="flex items-center gap-1 font-medium">
              {pct ? "Percent" : `Price${instrument?.currency ? ` (${instrument.currency})` : ""}`}
              {kind === "volatility_above" ? (
                <InfoTip label="About volatility">
                  Annualised standard deviation of the last 20 daily returns. Large stocks often sit
                  between 15% and 40%; crypto is often above 50%.
                </InfoTip>
              ) : null}
            </span>
            <input
              className={inputClass}
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={pct ? (kind === "move_pct" ? "5" : "40") : "0.00"}
            />
          </label>
        ) : (
          <p className="self-end text-xs text-muted">
            Fires when the daily scan flags an unusual move, volume, volatility or correlation for
            this asset.
          </p>
        )}
      </div>
      {localError || m.create.error ? (
        <p role="alert" className="text-sm text-negative">
          {localError ?? errorMessage(m.create.error)}
        </p>
      ) : null}
      <div className="flex gap-2">
        <button type="submit" className={primaryClass} disabled={m.create.isPending}>
          Create alert
        </button>
        <button type="button" className={buttonClass} onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function RecentAnomalies() {
  const q = useAnomalies(null, 14);
  return (
    <Card>
      <CardHeader
        title="Unusual activity, last 14 days"
        subtitle="Statistical flags across all tracked assets"
        action={
          <InfoTip label="How anomalies are flagged">
            Each day is compared with that asset&apos;s own previous year using a robust z-score
            (median and median absolute deviation). A day is flagged when the move is at least 4
            typical deviations away (3.5 for volatility and correlation). Flags describe what
            happened; they are not buy or sell signals.
          </InfoTip>
        }
      />
      <QueryState query={q} skeletonLines={5}>
        {(list) => (
          <AnomalyList
            items={list}
            showInstrument
            empty="No unusual activity flagged in the last 14 days."
          />
        )}
      </QueryState>
    </Card>
  );
}
