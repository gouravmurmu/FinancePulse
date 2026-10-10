import { Fragment } from "react";
import { cn } from "@/lib/cn";

const LABELS: Record<string, string> = {
  Fact: "border-accent/40 text-accent",
  Computed: "border-positive/40 text-positive",
  "Model estimate": "border-warning/40 text-warning",
  Hypothesis: "border-border text-muted",
};
const TOKEN = /(\*\*[^*]+\*\*|\[(?:Fact|Computed|Model estimate|Hypothesis)\])/g;

// Citation markers some models add (e.g. 【get_risk】); sources are listed separately.
const CITATION = /\s*【[^】]*】/g;
const SEPARATOR = /^:?-{3,}:?$/;
const ROW_BREAK = "\u0000";

function inline(text: string) {
  return text
    .replace(CITATION, "")
    .split(TOKEN)
    .map((part, i) => {
      if (!part) return null;
      const label = part.match(/^\[(Fact|Computed|Model estimate|Hypothesis)\]$/)?.[1];
      if (label) {
        return (
          <span
            key={i}
            className={cn(
              "mr-1 inline-block rounded-full border px-1.5 text-[11px] leading-4 font-medium",
              LABELS[label],
            )}
          >
            {label}
          </span>
        );
      }
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      return <Fragment key={i}>{part}</Fragment>;
    });
}

/** Rows of a Markdown table. Also copes with a table squashed onto one line
 * ("| a | b | | c | d |"), using the |---| separator to find the column count. */
export function parseTable(lines: string[]): string[][] | null {
  const tokens: string[] = [];
  for (const line of lines) {
    if (tokens.length) tokens.push(ROW_BREAK);
    tokens.push(
      ...line
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((c) => c.trim()),
    );
  }
  let n = 0;
  for (let i = 0; i < tokens.length && !n; i++) {
    let run = 0;
    while (SEPARATOR.test(tokens[i + run] ?? "")) run++;
    n = run;
  }
  if (n < 2) return null;
  const rows: string[][] = [];
  let cur: string[] = [];
  for (const t of tokens) {
    if (t === ROW_BREAK) {
      if (cur.length) rows.push(cur);
      cur = [];
      continue;
    }
    if (cur.length >= n) {
      rows.push(cur);
      cur = [];
      if (t === "") continue;
    }
    cur.push(t);
  }
  if (cur.length) rows.push(cur);
  const body = rows
    .map((r) => (r[0] === "" && r.length > n ? r.slice(1) : r))
    .filter((r) => r.some((c) => c) && !r.every((c) => !c || SEPARATOR.test(c)))
    .map((r) => Array.from({ length: n }, (_, i) => r[i] ?? ""));
  return body.length >= 2 ? body : null;
}

function Table({ rows }: { rows: string[][] }) {
  const [head, ...body] = rows;
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface-raised text-muted">
          <tr>
            {head.map((c, i) => (
              <th
                key={i}
                scope="col"
                className={cn("px-3 py-2 font-medium", i > 0 && "text-right")}
              >
                {inline(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {r.map((c, j) =>
                j === 0 ? (
                  <th key={j} scope="row" className="px-3 py-2 font-normal text-muted">
                    {inline(c)}
                  </th>
                ) : (
                  <td key={j} className="px-3 py-2 text-right tabular-nums">
                    {inline(c)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Block = { kind: "p" | "ul" | "table"; lines: string[] };

/** A small, safe subset of Markdown: paragraphs, bullets, tables, bold and claim
 * labels. Never renders HTML from the model. */
export function AnswerText({ text }: { text: string }) {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const prev = blocks[blocks.length - 1];
    if (line.startsWith("|")) {
      if (prev?.kind === "table") prev.lines.push(line);
      else blocks.push({ kind: "table", lines: [line] });
      continue;
    }
    if (!line) {
      blocks.push({ kind: "p", lines: [] });
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.*)$/) ?? line.match(/^\d+[.)]\s+(.*)$/);
    const last = blocks[blocks.length - 1];
    if (bullet) {
      if (last?.kind === "ul") last.lines.push(bullet[1]);
      else blocks.push({ kind: "ul", lines: [bullet[1]] });
    } else if (last?.kind === "p" && last.lines.length) {
      last.lines.push(line.replace(/^#+\s*/, ""));
    } else {
      blocks.push({ kind: "p", lines: [line.replace(/^#+\s*/, "")] });
    }
  }
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed">
      {blocks
        .filter((b) => b.lines.length)
        .map((b, i) => {
          if (b.kind === "table") {
            const rows = parseTable(b.lines);
            return rows ? (
              <Table key={i} rows={rows} />
            ) : (
              <p key={i}>{inline(b.lines.join(" "))}</p>
            );
          }
          return b.kind === "ul" ? (
            <ul key={i} className="ml-4 list-disc space-y-1">
              {b.lines.map((l, j) => (
                <li key={j}>{inline(l)}</li>
              ))}
            </ul>
          ) : (
            <p key={i}>{inline(b.lines.join(" "))}</p>
          );
        })}
    </div>
  );
}
