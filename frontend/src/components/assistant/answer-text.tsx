import { Fragment } from "react";
import { cn } from "@/lib/cn";

const LABELS: Record<string, string> = {
  Fact: "border-accent/40 text-accent",
  Computed: "border-positive/40 text-positive",
  "Model estimate": "border-warning/40 text-warning",
  Hypothesis: "border-border text-muted",
};
const TOKEN = /(\*\*[^*]+\*\*|\[(?:Fact|Computed|Model estimate|Hypothesis)\])/g;

function inline(text: string) {
  return text.split(TOKEN).map((part, i) => {
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

/** A small, safe subset of Markdown: paragraphs, bullets, bold and claim labels.
 * Never renders HTML from the model. */
export function AnswerText({ text }: { text: string }) {
  const blocks: { kind: "p" | "ul"; lines: string[] }[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
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
        .map((b, i) =>
          b.kind === "ul" ? (
            <ul key={i} className="ml-4 list-disc space-y-1">
              {b.lines.map((l, j) => (
                <li key={j}>{inline(l)}</li>
              ))}
            </ul>
          ) : (
            <p key={i}>{inline(b.lines.join(" "))}</p>
          ),
        )}
    </div>
  );
}
