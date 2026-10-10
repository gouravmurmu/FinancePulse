export const inputClass =
  "w-full rounded-lg border border-border bg-bg px-3 py-2 text-base outline-none focus:border-accent";
export const buttonClass =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-surface-raised px-3 py-1.5 text-sm font-medium hover:border-accent disabled:opacity-50";
export const primaryClass =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-contrast disabled:opacity-50";

export function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) return String(err.message);
  return "Something went wrong. Please try again.";
}
