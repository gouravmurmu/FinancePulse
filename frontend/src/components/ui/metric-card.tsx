import { cn } from "@/lib/cn";
import { Card } from "./card";
import { FreshnessChip, type Freshness } from "./freshness-chip";

export function MetricCard({
  label,
  value,
  hint,
  freshness,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  freshness?: Freshness;
  tone?: "default" | "positive" | "negative" | "warning" | "muted";
}) {
  const toneClass = {
    default: "text-text",
    positive: "text-positive",
    negative: "text-negative",
    warning: "text-warning",
    muted: "text-subtle",
  }[tone];
  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <span className="label">{label}</span>
        {freshness ? <FreshnessChip freshness={freshness} /> : null}
      </div>
      <div className={cn("num mt-2 text-lg font-semibold", toneClass)}>{value}</div>
      {hint ? <div className="mt-1 text-sm text-muted">{hint}</div> : null}
    </Card>
  );
}
