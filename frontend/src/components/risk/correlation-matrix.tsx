import { formatNumber } from "@/lib/format";
import { divergingColor } from "@/lib/series";

/** Correlation table; every cell prints its value, colour is secondary. */
export function CorrelationMatrix({
  ids,
  matrix,
  names,
}: {
  ids: string[];
  matrix: number[][];
  names: Record<string, string>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="num w-full border-separate border-spacing-0.5 text-sm">
        <caption className="sr-only">Correlation of daily returns</caption>
        <thead>
          <tr>
            <th scope="col" className="sr-only">
              Instrument
            </th>
            {ids.map((id) => (
              <th
                key={id}
                scope="col"
                className="max-w-24 truncate px-2 py-1 text-xs font-medium text-muted"
                title={names[id]}
              >
                {names[id] ?? id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ids.map((row, r) => (
            <tr key={row}>
              <th
                scope="row"
                className="max-w-32 truncate pr-2 text-left text-xs font-medium text-muted"
                title={names[row]}
              >
                {names[row] ?? row}
              </th>
              {ids.map((col, c) => {
                const v = matrix[r][c];
                return (
                  <td
                    key={col}
                    className="h-10 min-w-14 rounded-md text-center font-medium"
                    style={{
                      background: divergingColor(v),
                      color: Math.abs(v) > 0.6 ? "#fff" : "var(--text)",
                    }}
                    title={`${names[row]} vs ${names[col]}: ${formatNumber(v)}`}
                  >
                    {formatNumber(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex items-center gap-2 text-xs text-subtle" aria-hidden="true">
        <span>−1 opposite</span>
        <span
          className="h-2 w-32 rounded"
          style={{
            background: "linear-gradient(90deg, var(--div-neg), var(--div-mid), var(--div-pos))",
          }}
        />
        <span>+1 together</span>
      </div>
    </div>
  );
}
