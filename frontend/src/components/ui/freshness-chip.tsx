import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

/** Every number group carries one of these. See docs/DESIGN_SYSTEM.md. */
export type Freshness =
  | { kind: "live" }
  | { kind: "delayed"; minutes: number }
  | { kind: "eod"; asOf: string }
  | { kind: "stale"; asOf: string }
  | { kind: "unavailable" }
  | { kind: "demo" };

export function freshnessLabel(f: Freshness): string {
  switch (f.kind) {
    case "live":
      return "Live";
    case "delayed":
      return `Delayed ${f.minutes} min`;
    case "eod":
      return `End of day · ${formatDate(f.asOf).replace(/ \d{4}$/, "")}`;
    case "stale":
      return `Stale · ${formatDate(f.asOf)}`;
    case "unavailable":
      return "Unavailable";
    case "demo":
      return "Demo data";
  }
}

const STYLE: Record<Freshness["kind"], string> = {
  live: "text-positive border-positive/30",
  delayed: "text-muted border-border",
  eod: "text-muted border-border",
  stale: "text-warning border-warning/40",
  unavailable: "text-subtle border-border",
  demo: "text-warning border-warning/40",
};

export function FreshnessChip({
  freshness,
  className,
}: {
  freshness: Freshness;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "num inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        STYLE[freshness.kind],
        className,
      )}
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {freshnessLabel(freshness)}
    </span>
  );
}
