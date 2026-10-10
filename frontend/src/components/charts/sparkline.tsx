/** Tiny trend line beside a number. Decorative: the number carries the value. */
export function Sparkline({
  values,
  className,
  width = 96,
  height = 28,
}: {
  values: number[];
  className?: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return <span className={className} style={{ width, height }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const d = values
    .map(
      (v, i) =>
        `${i ? "L" : "M"}${(i * step).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`,
    )
    .join("");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg
      aria-hidden="true"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
    >
      <path
        d={d}
        fill="none"
        stroke={up ? "var(--positive)" : "var(--negative)"}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
