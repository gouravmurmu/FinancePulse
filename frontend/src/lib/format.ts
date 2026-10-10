/**
 * Shared number and date formatting. See docs/DESIGN_SYSTEM.md:
 * currency symbol always shown, percentages to 2 decimals, large numbers
 * abbreviated, dates as "10 Oct 2026", Indian grouping when INR is selected.
 */

export type Currency = "USD" | "INR";

const SYMBOL: Record<Currency, string> = { USD: "$", INR: "₹" };
const MINUS = "−"; // U+2212, typographic minus

function sign(value: number): string {
  if (value > 0) return "+";
  if (value < 0) return MINUS;
  return "";
}

/** Full-precision money, e.g. "$1,234.50" or "₹12,34,567.00". */
export function formatMoney(value: number, currency: Currency, decimals = 2): string {
  const locale = currency === "INR" ? "en-IN" : "en-US";
  const body = new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value));
  return `${value < 0 ? MINUS : ""}${SYMBOL[currency]}${body}`;
}

/**
 * Abbreviated number. INR uses lakh (L, 1e5) and crore (Cr, 1e7);
 * everything else uses K / M / B / T.
 */
export function abbreviate(value: number, currency?: Currency): string {
  const abs = Math.abs(value);
  const neg = value < 0 ? MINUS : "";
  const prefix = currency ? SYMBOL[currency] : "";
  const fmt = (n: number, suffix: string) =>
    `${neg}${prefix}${Number(n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2))}${suffix}`;

  if (currency === "INR") {
    if (abs >= 1e7) return fmt(abs / 1e7, "Cr");
    if (abs >= 1e5) return fmt(abs / 1e5, "L");
    if (abs >= 1e3) return fmt(abs / 1e3, "K");
    return fmt(abs, "");
  }
  if (abs >= 1e12) return fmt(abs / 1e12, "T");
  if (abs >= 1e9) return fmt(abs / 1e9, "B");
  if (abs >= 1e6) return fmt(abs / 1e6, "M");
  if (abs >= 1e3) return fmt(abs / 1e3, "K");
  return fmt(abs, "");
}

/** Percentage from a fraction (0.0123 -> "+1.23%"). */
export function formatPercent(fraction: number, { signed = true } = {}): string {
  const body = Math.abs(fraction * 100).toFixed(2);
  const s = signed ? sign(fraction) : fraction < 0 ? MINUS : "";
  return `${s}${body}%`;
}

/** Direction glyph so gains and losses never rely on color alone. */
export function direction(value: number): "▲" | "▼" | "•" {
  if (value > 0) return "▲";
  if (value < 0) return "▼";
  return "•";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "10 Oct 2026" in the given IANA time zone (default UTC). */
export function formatDate(input: string | Date, timeZone = "UTC"): string {
  const d = typeof input === "string" ? new Date(input) : input;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "numeric",
    month: "numeric",
    year: "numeric",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return `${get("day")} ${MONTHS[get("month") - 1]} ${get("year")}`;
}
