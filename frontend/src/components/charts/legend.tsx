export type LegendItem = { id: string; label: string; color: string; value?: string };

export function Legend({ items }: { items: LegendItem[] }) {
  if (items.length < 2) return null;
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Legend">
      {items.map((it) => (
        <li key={it.id} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-3 rounded"
            style={{ background: it.color }}
          />
          <span className="text-muted">{it.label}</span>
          {it.value ? <span className="num font-medium text-text">{it.value}</span> : null}
        </li>
      ))}
    </ul>
  );
}
