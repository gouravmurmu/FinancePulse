import type { Metadata } from "next";
import { PlannedSection } from "@/components/system/planned-section";

export const metadata: Metadata = { title: "Portfolio" };

export default function PortfolioPage() {
  return (
    <PlannedSection
      title="Portfolio"
      step={3}
      summary="Track holdings from a transaction ledger, with private data visible only to you."
      features={[
        "Buy and sell ledger with fees and currency",
        "Average cost, realized and unrealized P&L",
        "Allocation by asset class, currency and sector",
        "Performance against a benchmark",
        "Stress scenarios with your own shocks",
        "CSV import and export",
      ]}
    />
  );
}
