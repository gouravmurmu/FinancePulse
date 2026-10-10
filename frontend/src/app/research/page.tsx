import type { Metadata } from "next";
import { PlannedSection } from "@/components/system/planned-section";

export const metadata: Metadata = { title: "Research" };

export default function ResearchPage() {
  return (
    <PlannedSection
      title="Research"
      step={2}
      summary="Search any supported instrument and open a page with its chart, indicators, risk metrics, fundamentals and news."
      features={[
        "Search by name, symbol or alias",
        "Line and candlestick charts with volume",
        "SMA, EMA, RSI, MACD and Bollinger Bands",
        "Fundamentals where a reliable source exists",
        "Crypto supply and volatility, metal reference prices",
        "Related instruments and headlines",
      ]}
    />
  );
}
