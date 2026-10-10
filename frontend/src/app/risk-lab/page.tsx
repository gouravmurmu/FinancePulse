import type { Metadata } from "next";
import { PlannedSection } from "@/components/system/planned-section";

export const metadata: Metadata = { title: "Risk Lab" };

export default function RiskLabPage() {
  return (
    <PlannedSection
      title="Risk Lab"
      step={2}
      summary="Measure and compare risk across assets with documented, tested calculations."
      features={[
        "Volatility, CAGR, Sharpe and Sortino",
        "Max drawdown with drawdown chart",
        "Historical VaR and expected shortfall",
        "Correlation matrix and rolling correlation",
        "Stress tests",
        "Seeded Monte Carlo simulation",
      ]}
    />
  );
}
