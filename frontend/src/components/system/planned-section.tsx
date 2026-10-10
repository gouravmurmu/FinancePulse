import { Card } from "@/components/ui/card";

/** Honest placeholder for a section that ships in a later build step. */
export function PlannedSection({
  title,
  step,
  summary,
  features,
}: {
  title: string;
  step: number;
  summary: string;
  features: string[];
}) {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-1 max-w-prose text-muted">{summary}</p>
      </header>
      <Card>
        <p className="label">Not built yet · arrives in build step {step}</p>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {features.map((f) => (
            <li key={f} className="flex gap-2 text-muted">
              <span aria-hidden="true" className="text-accent">
                •
              </span>
              {f}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
