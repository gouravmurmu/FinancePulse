import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreshnessChip, freshnessLabel } from "./freshness-chip";

describe("FreshnessChip", () => {
  it("labels each state distinctly", () => {
    const labels = [
      freshnessLabel({ kind: "live" }),
      freshnessLabel({ kind: "delayed", minutes: 15 }),
      freshnessLabel({ kind: "eod", asOf: "2026-10-09T16:00:00Z" }),
      freshnessLabel({ kind: "stale", asOf: "2026-10-01T16:00:00Z" }),
      freshnessLabel({ kind: "unavailable" }),
      freshnessLabel({ kind: "demo" }),
    ];
    expect(labels).toEqual([
      "Live",
      "Delayed 15 min",
      "End of day · 9 Oct",
      "Stale · 1 Oct 2026",
      "Unavailable",
      "Demo data",
    ]);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("renders the label text", () => {
    render(<FreshnessChip freshness={{ kind: "delayed", minutes: 15 }} />);
    expect(screen.getByText("Delayed 15 min")).toBeInTheDocument();
  });
});
