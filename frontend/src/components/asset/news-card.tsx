"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { TableView } from "@/components/charts/table-view";
import { Card, CardHeader } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { QueryState } from "@/components/ui/query-state";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";
import { marketApi, type News, type NewsArticle } from "@/lib/market";

const SENTIMENT = {
  positive: { label: "Positive", cls: "border-positive/40 text-positive" },
  neutral: { label: "Neutral", cls: "border-border text-muted" },
  negative: { label: "Negative", cls: "border-negative/40 text-negative" },
} as const;

function timeAgo(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 60) return `${Math.max(mins, 1)} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return formatDate(iso);
}

/** Headlines with attribution and FinBERT tone. Tone describes the headline only. */
export function NewsCard({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["news", id], queryFn: () => marketApi.news(id) });
  return (
    <Card>
      <CardHeader
        title="News"
        subtitle="Headlines from Finnhub, linked to the original source"
        action={
          <InfoTip label="About headline tone">
            Each headline is classified by FinBERT, a language model trained on financial text, as
            positive, neutral or negative. It reads the headline only, can be wrong, and says
            nothing about where the price will go.
          </InfoTip>
        }
      />
      <QueryState query={q} skeletonLines={4}>
        {(d) => <NewsBody d={d} />}
      </QueryState>
    </Card>
  );
}

function NewsBody({ d }: { d: News }) {
  if (d.coverage_note && d.articles.length === 0) {
    return <p className="text-sm text-muted">{d.coverage_note}</p>;
  }
  if (!d.configured) {
    return (
      <p className="text-sm text-muted">
        News is not switched on for this deployment yet (it needs a free Finnhub API key).
      </p>
    );
  }
  if (d.articles.length === 0) {
    return <p className="text-sm text-muted">No headlines in the last few days.</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      {d.trend.points.length >= 3 ? <ToneStrip d={d} /> : null}
      <ul className="flex flex-col divide-y divide-border">
        {d.articles.slice(0, 8).map((a) => (
          <Headline key={a.id} a={a} />
        ))}
      </ul>
      {d.coverage_note ? <p className="text-xs text-subtle">{d.coverage_note}</p> : null}
    </div>
  );
}

function Headline({ a }: { a: NewsArticle }) {
  const s = a.sentiment ? SENTIMENT[a.sentiment.label] : null;
  return (
    <li className="py-2.5">
      <a
        href={a.url}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="group inline-flex items-start gap-1.5 text-sm font-medium hover:underline"
      >
        <span>{a.headline}</span>
        <ExternalLink
          size={13}
          aria-hidden="true"
          className="mt-1 shrink-0 text-subtle group-hover:text-text"
        />
        <span className="sr-only">(opens {a.source} in a new tab)</span>
      </a>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-subtle">
        <span>{a.source}</span>
        <span aria-hidden="true">·</span>
        <time dateTime={a.published_at}>{timeAgo(a.published_at)}</time>
        {s && a.sentiment ? (
          <span
            className={cn("rounded-full border px-1.5 py-px", s.cls)}
            title={`FinBERT, ${Math.round((a.sentiment.score ?? 0) * 100)}% confidence`}
          >
            {s.label}
            <span className="sr-only">
              {" "}
              tone, {Math.round((a.sentiment.score ?? 0) * 100)}% confidence
            </span>
          </span>
        ) : null}
      </div>
    </li>
  );
}

/** Daily headline tone as bars, for exploration only. */
function ToneStrip({ d }: { d: News }) {
  const W = 600;
  const H = 64;
  const end = new Date();
  const start = new Date(end.getTime() - d.trend.days * 86_400_000);
  const x = (iso: string) =>
    ((new Date(iso).getTime() - start.getTime()) / (end.getTime() - start.getTime())) * W;
  const bw = Math.max(2, W / d.trend.days - 1);
  const closes = d.trend.close.map((c) => c.value);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  const price = d.trend.close
    .map(
      (c) =>
        `${x(c.date).toFixed(1)},${(H - 2 - ((c.value - lo) / (hi - lo || 1)) * (H - 4)).toFixed(1)}`,
    )
    .join(" ");
  return (
    <figure>
      <figcaption className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-xs text-muted">
        <span>Daily headline tone (bars) and closing price (line), last {d.trend.days} days</span>
        <span className="text-subtle">Exploratory: tone does not explain or predict price</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-16 w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label="Bars above the middle are days with mostly positive headlines, below are mostly negative; the line is the closing price"
      >
        <line x1={0} x2={W} y1={H / 2} y2={H / 2} className="stroke-border" strokeWidth={1} />
        {d.trend.points.map((p) => {
          const h = (Math.abs(p.tone) * (H / 2 - 2)) | 0 || 1;
          return (
            <rect
              key={p.date}
              x={x(p.date) - bw / 2}
              width={bw}
              y={p.tone >= 0 ? H / 2 - h : H / 2}
              height={h}
              className={p.tone >= 0 ? "fill-positive/70" : "fill-negative/70"}
            />
          );
        })}
        {closes.length > 1 ? (
          <polyline
            points={price}
            fill="none"
            className="stroke-text/60"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
        ) : null}
      </svg>
      <TableView
        caption="Daily headline tone"
        columns={["Date", "Headlines", "Net tone (−1 to +1)"]}
        rows={d.trend.points.map((p) => [formatDate(p.date), p.headlines, p.tone.toFixed(2)])}
      />
    </figure>
  );
}
