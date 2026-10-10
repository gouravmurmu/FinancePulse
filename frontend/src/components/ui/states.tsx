import { cn } from "@/lib/cn";
import { Card } from "./card";

export function SkeletonBlock({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-surface-raised", className)} />;
}

export function SkeletonCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <Card className={className} aria-busy="true" aria-label="Loading">
      <SkeletonBlock className="mb-3 h-4 w-1/3" />
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBlock key={i} className="mb-2 h-3 w-full last:w-2/3" />
      ))}
    </Card>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      {icon ? <div className="mb-1 text-accent">{icon}</div> : null}
      <h2 className="text-md font-semibold">{title}</h2>
      <p className="max-w-prose text-muted">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </Card>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
}: {
  title?: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <Card role="alert" className="border-negative/30">
      <h2 className="font-semibold text-negative">{title}</h2>
      <p className="mt-1 text-muted">{description}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-border bg-surface-raised px-3 py-1.5 text-sm font-medium hover:border-accent"
        >
          Try again
        </button>
      ) : null}
    </Card>
  );
}
