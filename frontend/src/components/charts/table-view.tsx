"use client";

import { Table2 } from "lucide-react";

/** Every chart has an accessible table twin, collapsed by default. */
export function TableView({
  caption,
  columns,
  rows,
  maxRows = 400,
}: {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
  maxRows?: number;
}) {
  const shown = rows.length > maxRows ? rows.slice(-maxRows) : rows;
  return (
    <details className="mt-3 text-sm">
      <summary className="inline-flex cursor-pointer items-center gap-1.5 text-muted hover:text-text">
        <Table2 size={14} aria-hidden="true" /> Table view
      </summary>
      <div className="mt-2 max-h-72 overflow-auto rounded-lg border border-border">
        <table className="num w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 bg-surface-raised">
            <tr>
              {columns.map((c) => (
                <th key={c} scope="col" className="px-3 py-1.5 font-medium text-muted">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i} className="border-t border-border">
                {r.map((cell, j) => (
                  <td key={j} className="px-3 py-1">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > maxRows ? (
        <p className="mt-1 text-xs text-subtle">
          Showing the latest {maxRows} of {rows.length} rows.
        </p>
      ) : null}
    </details>
  );
}
