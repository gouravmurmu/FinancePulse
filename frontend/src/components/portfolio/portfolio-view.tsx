"use client";

import Link from "next/link";
import { BriefcaseBusiness, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { DownloadButton, fileSlug, fileStamp } from "@/components/reports/download-button";
import { Card } from "@/components/ui/card";
import { QueryState } from "@/components/ui/query-state";
import { Segmented } from "@/components/ui/segmented";
import { EmptyState, SkeletonCard } from "@/components/ui/states";
import {
  useAuthedApi,
  usePortfolioMutations,
  usePortfolios,
  type Portfolio,
} from "@/lib/portfolio";
import { buttonClass, errorMessage, inputClass, primaryClass } from "./forms";
import { Overview } from "./overview";
import { PerformancePanel } from "./performance";
import { Rebalance } from "./rebalance";
import { StressPanel } from "./stress";
import { Transactions } from "./transactions";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "performance", label: "Performance" },
  { value: "transactions", label: "Transactions" },
  { value: "stress", label: "Stress test" },
  { value: "rebalance", label: "Rebalance" },
] as const;
type Tab = (typeof TABS)[number]["value"];

const LAST_KEY = "marketpulse.portfolio";

export function PortfolioView() {
  const { ready, configured, session } = useAuth();
  if (!ready) return <SkeletonCard lines={4} />;
  if (!configured) {
    return (
      <EmptyState
        icon={<BriefcaseBusiness size={28} />}
        title="Portfolios need sign-in"
        description="This deployment has no sign-in configured, so portfolios are switched off. Markets, Research and Risk Lab still work."
      />
    );
  }
  if (!session) {
    return (
      <EmptyState
        icon={<BriefcaseBusiness size={28} />}
        title="Track your portfolio privately"
        description="Record buys and sells to see average cost, profit and loss, allocation, performance against a benchmark and stress tests. Your data is visible only to you."
        action={
          <Link href="/sign-in?next=/portfolio" className={primaryClass}>
            Sign in or create an account
          </Link>
        }
      />
    );
  }
  return <SignedIn />;
}

function SignedIn() {
  const portfolios = usePortfolios();
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const list = portfolios.data;
    if (!list?.length) return;
    if (selected && list.some((p) => p.id === selected)) return;
    let last: string | null = null;
    try {
      last = localStorage.getItem(LAST_KEY);
    } catch {}
    setSelected(list.find((p) => p.id === last)?.id ?? list[0].id);
  }, [portfolios.data, selected]);

  function choose(id: string) {
    setSelected(id);
    try {
      localStorage.setItem(LAST_KEY, id);
    } catch {}
  }

  return (
    <QueryState query={portfolios}>
      {(list) => {
        const current = list.find((p) => p.id === selected) ?? null;
        if (!list.length || creating) {
          return (
            <CreatePortfolio
              first={!list.length}
              onCancel={list.length ? () => setCreating(false) : undefined}
              onCreated={(p) => {
                setCreating(false);
                choose(p.id);
                setTab("transactions");
              }}
            />
          );
        }
        return (
          <div className="flex flex-col gap-6">
            <PortfolioHeader
              list={list}
              current={current}
              onChoose={choose}
              onNew={() => setCreating(true)}
            />
            <Segmented label="Portfolio section" options={TABS} value={tab} onChange={setTab} />
            {current ? (
              <>
                {tab === "overview" ? (
                  <Overview portfolio={current} onAdd={() => setTab("transactions")} />
                ) : null}
                {tab === "performance" ? <PerformancePanel portfolio={current} /> : null}
                {tab === "transactions" ? <Transactions portfolio={current} /> : null}
                {tab === "stress" ? <StressPanel portfolio={current} /> : null}
                {tab === "rebalance" ? <Rebalance portfolio={current} /> : null}
              </>
            ) : null}
          </div>
        );
      }}
    </QueryState>
  );
}

function PortfolioHeader({
  list,
  current,
  onChoose,
  onNew,
}: {
  list: Portfolio[];
  current: Portfolio | null;
  onChoose: (id: string) => void;
  onNew: () => void;
}) {
  const { remove } = usePortfolioMutations();
  const api = useAuthedApi();
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <h1 className="text-xl font-semibold">Portfolio</h1>
        <p className="text-sm text-muted">
          Private to you. Valued at end-of-day prices in{" "}
          {current?.base_currency === "INR" ? "Indian rupees" : "US dollars"}.
        </p>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="portfolio-select">
          Portfolio
        </label>
        <select
          id="portfolio-select"
          value={current?.id ?? ""}
          onChange={(e) => onChoose(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm"
        >
          {list.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.base_currency})
            </option>
          ))}
        </select>
        {current && current.transaction_count > 0 ? (
          <>
            <DownloadButton
              kind="pdf"
              label="Report"
              className={buttonClass}
              filename={`${fileSlug(current.name)}-${fileStamp()}.pdf`}
              fetchBlob={() => api.blob(`/api/v1/reports/portfolio/${current.id}/pdf`)}
            />
            <DownloadButton
              label="Holdings CSV"
              className={buttonClass}
              filename={`${fileSlug(current.name)}-holdings-${fileStamp()}.csv`}
              fetchBlob={() => api.blob(`/api/v1/reports/portfolio/${current.id}/csv`)}
            />
          </>
        ) : null}
        <button type="button" className={buttonClass} onClick={onNew}>
          <Plus size={16} aria-hidden="true" /> New
        </button>
        {current ? (
          <button
            type="button"
            className={buttonClass}
            aria-label={`Delete portfolio ${current.name}`}
            disabled={remove.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Delete "${current.name}" and its ${current.transaction_count} transactions? This can't be undone.`,
                )
              ) {
                remove.mutate(current.id);
              }
            }}
          >
            <Trash2 size={16} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function CreatePortfolio({
  first,
  onCancel,
  onCreated,
}: {
  first: boolean;
  onCancel?: () => void;
  onCreated: (p: Portfolio) => void;
}) {
  const { create } = usePortfolioMutations();
  const [name, setName] = useState(first ? "My portfolio" : "");
  const [base, setBase] = useState<"USD" | "INR">("USD");
  return (
    <Card className="mx-auto w-full max-w-lg">
      <h1 className="text-lg font-semibold">
        {first ? "Create your first portfolio" : "New portfolio"}
      </h1>
      <p className="mt-1 text-sm text-muted">
        Choose the currency you think in. Holdings in other currencies are converted at each
        day&apos;s USD/INR close, and currency gains are shown separately.
      </p>
      <form
        className="mt-4 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name, base_currency: base }, { onSuccess: onCreated });
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          <span className="label">Name</span>
          <input
            required
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
          />
        </label>
        <div className="flex flex-col gap-1 text-sm">
          <span className="label">Base currency</span>
          <Segmented
            label="Base currency"
            options={[
              { value: "USD", label: "US dollar ($)" },
              { value: "INR", label: "Indian rupee (₹)" },
            ]}
            value={base}
            onChange={setBase}
          />
          <span className="text-xs text-subtle">
            Benchmark: {base === "INR" ? "NIFTY 50" : "S&P 500"} (you can change it later).
          </span>
        </div>
        {create.error ? (
          <p role="alert" className="text-sm text-negative">
            {errorMessage(create.error)}
          </p>
        ) : null}
        <div className="flex gap-2">
          <button type="submit" className={primaryClass} disabled={create.isPending}>
            Create portfolio
          </button>
          {onCancel ? (
            <button type="button" className={buttonClass} onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>
    </Card>
  );
}
