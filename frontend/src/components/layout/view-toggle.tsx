"use client";

import { cn } from "@/lib/cn";
import { useViewMode, type ViewMode } from "@/lib/view-mode";

const OPTIONS: { value: ViewMode; label: string; hint: string }[] = [
  { value: "simple", label: "Simple", hint: "Key numbers with explanations" },
  { value: "pro", label: "Pro", hint: "Adds full tables, indicators and model details" },
];

export function ViewToggle() {
  const [mode, setMode] = useViewMode();
  return (
    <div
      role="radiogroup"
      aria-label="Detail level"
      className="hidden items-center rounded-lg border border-border p-0.5 text-sm sm:flex"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={mode === o.value}
          title={o.hint}
          onClick={() => setMode(o.value)}
          className={cn(
            "rounded-md px-2.5 py-1",
            mode === o.value
              ? "bg-surface-raised font-medium text-text"
              : "text-muted hover:text-text",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
