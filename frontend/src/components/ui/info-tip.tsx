"use client";

import { Info } from "lucide-react";
import { useId, useState } from "react";

/** ⓘ explainer: what a metric means and how to read it. Hover, focus or tap. */
export function InfoTip({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onBlur={() => setOpen(false)}
        className="rounded-full text-subtle hover:text-text"
      >
        <Info size={13} aria-hidden="true" />
      </button>
      {open ? (
        <span
          id={id}
          role="tooltip"
          className="absolute left-1/2 top-5 z-40 w-64 -translate-x-1/2 rounded-lg border border-border bg-surface-raised p-2.5 text-xs font-normal normal-case leading-relaxed tracking-normal text-text shadow-card"
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}
