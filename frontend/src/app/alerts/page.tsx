import type { Metadata } from "next";
import { PlannedSection } from "@/components/system/planned-section";

export const metadata: Metadata = { title: "Alerts" };

export default function AlertsPage() {
  return (
    <PlannedSection
      title="Alerts"
      step={3}
      summary="Get notified about price thresholds, large moves and unusual volatility, checked on a stated schedule."
      features={[
        "Price and percentage-move alerts",
        "Volatility and anomaly alerts",
        "In-app alert history",
        "Email delivery when configured",
      ]}
    />
  );
}
