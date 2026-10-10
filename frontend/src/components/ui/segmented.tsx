"use client";

import { cn } from "@/lib/cn";

/** Single-choice button group (radio semantics). */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: {
  label: string;
  options: readonly { value: T; label: string }[] | readonly T[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  const opts = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex flex-wrap rounded-lg border border-border bg-surface p-0.5",
        className,
      )}
    >
      {opts.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "rounded-md px-2.5 py-1 text-sm text-muted hover:text-text",
              active && "bg-surface-raised font-medium text-text shadow-card",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
