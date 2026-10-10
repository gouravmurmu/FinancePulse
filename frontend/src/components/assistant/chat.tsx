"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUp, Bot, Eraser, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { inputClass, primaryClass } from "@/components/portfolio/forms";
import { SkeletonBlock } from "@/components/ui/states";
import { ApiError } from "@/lib/api";
import {
  TOOL_LABEL,
  useAsk,
  useAssistantStatus,
  type AssistantContext,
  type ChatTurn,
} from "@/lib/assistant";
import { cn } from "@/lib/cn";
import { AnswerText } from "./answer-text";

const PORTFOLIO_KEY = "marketpulse.portfolio";

const SUGGESTIONS: Record<"asset" | "portfolio" | "general", string[]> = {
  asset: [
    "How risky has this been over the last year?",
    "Has anything unusual happened recently?",
    "What does the forecast check say, and can I trust it?",
  ],
  portfolio: [
    "Summarise my portfolio's risk",
    "What happens to my portfolio in an equity crash?",
    "Which holding moves my portfolio the most?",
  ],
  general: [
    "Compare Apple and Microsoft over the last year",
    "How volatile has Bitcoin been compared with gold?",
    "What do Nvidia's latest filings show?",
  ],
};

/** Works out what the user is looking at, so questions like "is this risky?" make sense. */
export function usePageContext(): { context: AssistantContext; kind: keyof typeof SUGGESTIONS } {
  const pathname = usePathname();
  const [portfolio, setPortfolio] = useState<string | null>(null);
  const asset = pathname.match(/^\/assets\/([^/]+)/)?.[1];
  const onPortfolio = pathname.startsWith("/portfolio");
  useEffect(() => {
    if (!onPortfolio) return;
    try {
      setPortfolio(localStorage.getItem(PORTFOLIO_KEY));
    } catch {
      setPortfolio(null);
    }
  }, [onPortfolio, pathname]);
  if (asset) return { context: { instrument_id: decodeURIComponent(asset) }, kind: "asset" };
  if (onPortfolio && portfolio) return { context: { portfolio_id: portfolio }, kind: "portfolio" };
  return { context: {}, kind: "general" };
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "The assistant did not respond. The server may be waking up; please try again.";
}

export function AssistantChat({ compact = false }: { compact?: boolean }) {
  const { ready, configured: authConfigured, session } = useAuth();
  const status = useAssistantStatus();
  const pathname = usePathname();

  if (!ready || status.isPending) {
    return (
      <div className="flex flex-col gap-2 p-1" aria-busy="true">
        <SkeletonBlock className="h-4 w-1/2" />
        <SkeletonBlock className="h-3 w-full" />
      </div>
    );
  }
  if (status.data && !status.data.configured) {
    return (
      <Notice title="The assistant is not switched on yet">
        This deployment has no AI key configured. Every other part of MarketPulse works without it.
      </Notice>
    );
  }
  if (!authConfigured) {
    return (
      <Notice title="The assistant needs sign-in">
        Sign-in is not configured on this deployment, so the assistant is off.
      </Notice>
    );
  }
  if (!session) {
    return (
      <Notice title="Sign in to ask questions">
        The assistant is free with a small daily allowance per account.
        <span className="mt-3 block">
          <Link href={`/sign-in?next=${encodeURIComponent(pathname)}`} className={primaryClass}>
            Sign in or create an account
          </Link>
        </span>
      </Notice>
    );
  }
  return <Conversation compact={compact} limit={status.data?.limits.requests_per_day} />;
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      <Bot size={28} aria-hidden="true" className="text-accent" />
      <h2 className="font-semibold">{title}</h2>
      <p className="max-w-prose text-sm text-muted">{children}</p>
    </div>
  );
}

function Conversation({ compact, limit }: { compact: boolean; limit?: number }) {
  const { context, kind } = usePageContext();
  const ask = useAsk();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [left, setLeft] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns, ask.isPending]);

  function submit(text: string) {
    const q = text.trim();
    if (!q || ask.isPending) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: q }];
    setTurns(next);
    setDraft("");
    ask.mutate(
      { turns: next, context },
      {
        onSuccess: (a) => {
          setTurns((t) => [...t, { role: "assistant", content: a.answer, meta: a }]);
          setLeft(a.usage.requests_left);
        },
        // Drop the unanswered question from history but keep it in the box to retry.
        onError: () => {
          setTurns((t) => t.slice(0, -1));
          setDraft(q);
        },
      },
    );
  }

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", compact ? "gap-3" : "gap-4")}>
      <div
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto"
        aria-live="polite"
        aria-busy={ask.isPending}
      >
        {turns.length === 0 ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted">
              {kind === "asset"
                ? "Ask about the asset you're viewing."
                : kind === "portfolio"
                  ? "Ask about the portfolio you're viewing."
                  : "Ask about any asset in MarketPulse, or about your portfolio."}{" "}
              Answers use MarketPulse data and say where each figure comes from.
            </p>
            <div className="flex flex-col items-start gap-2">
              {SUGGESTIONS[kind].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => submit(s)}
                  className="rounded-full border border-border px-3 py-1.5 text-left text-sm hover:border-accent hover:text-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div
              key={i}
              className="ml-8 self-end rounded-2xl rounded-br-sm bg-accent/10 px-3 py-2 text-sm"
            >
              <span className="sr-only">You asked: </span>
              {t.content}
            </div>
          ) : (
            <article key={i} className="flex flex-col gap-2">
              <span className="sr-only">Assistant answer:</span>
              <AnswerText text={t.content} />
              {t.meta ? <AnswerMeta meta={t.meta} /> : null}
            </article>
          ),
        )}
        {ask.isPending ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <span className="size-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
            Looking up the data…
          </p>
        ) : null}
        {ask.isError ? (
          <p role="alert" className="rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm">
            {errorText(ask.error)}
          </p>
        ) : null}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(draft);
        }}
        className="flex flex-col gap-1.5"
      >
        <div className="flex items-end gap-2">
          <label htmlFor="assistant-input" className="sr-only">
            Your question
          </label>
          <textarea
            id="assistant-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(draft);
              }
            }}
            rows={compact ? 2 : 2}
            maxLength={2000}
            placeholder="Ask a question…"
            className={cn(inputClass, "min-h-[44px] flex-1 resize-none")}
          />
          <button
            type="submit"
            disabled={!draft.trim() || ask.isPending}
            aria-label="Send question"
            className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-accent text-white disabled:opacity-40"
          >
            <ArrowUp size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-subtle">
          <span>
            Research aid, not investment advice.
            {left !== null
              ? ` ${left} question${left === 1 ? "" : "s"} left today.`
              : limit
                ? ` Up to ${limit} questions a day.`
                : ""}
          </span>
          {turns.length ? (
            <button
              type="button"
              onClick={() => {
                setTurns([]);
                ask.reset();
              }}
              className="inline-flex items-center gap-1 hover:text-text"
            >
              <Eraser size={12} aria-hidden="true" /> New conversation
            </button>
          ) : null}
        </div>
      </form>
    </div>
  );
}

function AnswerMeta({
  meta,
}: {
  meta: NonNullable<Extract<ChatTurn, { role: "assistant" }>["meta"]>;
}) {
  const tools = Array.from(new Set(meta.tool_calls.map((c) => TOOL_LABEL[c.tool] ?? c.tool)));
  return (
    <div className="flex flex-col gap-1 border-t border-border pt-2 text-xs text-subtle">
      {tools.length ? (
        <p className="flex flex-wrap items-center gap-1">
          <Wrench size={12} aria-hidden="true" />
          <span>Data used:</span>
          {tools.map((t) => (
            <span key={t} className="rounded-full bg-surface-raised px-1.5">
              {t}
            </span>
          ))}
        </p>
      ) : (
        <p>No MarketPulse data was looked up for this answer.</p>
      )}
      {meta.sources.length ? <p>Sources: {meta.sources.join("; ")}</p> : null}
      <p>{meta.disclaimer}</p>
    </div>
  );
}
