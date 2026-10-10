"use client";

import { Download, FileText, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/lib/api";

/** Fetches a report file and saves it. Shows progress because a sleeping
 * server can take a while to answer the first request. */
export function DownloadButton({
  label,
  filename,
  fetchBlob,
  kind = "file",
  className,
}: {
  label: string;
  filename: string;
  fetchBlob: () => Promise<Blob>;
  kind?: "pdf" | "file";
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const Icon = busy ? LoaderCircle : kind === "pdf" ? FileText : Download;

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const blob = await fetchBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Download failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={run}
        disabled={busy}
        aria-busy={busy}
        className={
          className ??
          "inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-sm text-muted hover:text-text disabled:opacity-60"
        }
      >
        <Icon size={15} aria-hidden="true" className={busy ? "animate-spin" : undefined} />
        {busy ? "Preparing…" : label}
      </button>
      {error ? (
        <span
          role="alert"
          className="absolute right-0 top-full z-10 mt-1 w-56 rounded-lg border border-warning/40 bg-surface p-2 text-xs"
        >
          {error}
        </span>
      ) : null}
    </span>
  );
}

export function fileStamp(): string {
  return new Date().toISOString().slice(0, 10);
}

export function fileSlug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "report"
  );
}
