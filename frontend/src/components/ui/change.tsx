import { cn } from "@/lib/cn";
import { direction, formatPercent } from "@/lib/format";

/** Signed percentage change with ▲/▼ so it never relies on colour alone. */
export function Change({
  value,
  className,
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value === null || value === undefined) {
    return <span className={cn("num text-subtle", className)}>—</span>;
  }
  const tone = value > 0 ? "text-positive" : value < 0 ? "text-negative" : "text-muted";
  return (
    <span className={cn("num font-medium", tone, className)}>
      <span aria-hidden="true">{direction(value)} </span>
      {formatPercent(value)}
    </span>
  );
}
