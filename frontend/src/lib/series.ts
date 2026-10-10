/**
 * Categorical series colours. A series keeps the slot of its position in the
 * user's selection, so removing one never repaints the others. At most 8.
 */
export const MAX_SERIES = 8;

export function seriesColor(slot: number): string {
  return `var(--chart-${(slot % MAX_SERIES) + 1})`;
}

/** Stable slot per id: reuse existing assignments, fill gaps for new ids. */
export function assignSlots(
  ids: string[],
  previous: Record<string, number> = {},
): Record<string, number> {
  const out: Record<string, number> = {};
  const used = new Set<number>();
  for (const id of ids) {
    const slot = previous[id];
    if (slot !== undefined && !used.has(slot)) {
      out[id] = slot;
      used.add(slot);
    }
  }
  for (const id of ids) {
    if (out[id] !== undefined) continue;
    let s = 0;
    while (used.has(s)) s++;
    out[id] = s;
    used.add(s);
  }
  return out;
}

/** Diverging colour for a correlation in [-1, 1]: red <-> grey <-> blue. */
export function divergingColor(value: number): string {
  const v = Math.max(-1, Math.min(1, value));
  const pct = Math.round(Math.abs(v) * 100);
  const pole = v >= 0 ? "var(--div-pos)" : "var(--div-neg)";
  return `color-mix(in oklab, ${pole} ${pct}%, var(--div-mid))`;
}
