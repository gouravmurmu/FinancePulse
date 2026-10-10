import type { Metadata } from "next";
import { PlannedSection } from "@/components/system/planned-section";

export const metadata: Metadata = { title: "AI Assistant" };

export default function AssistantPage() {
  return (
    <PlannedSection
      title="AI Assistant"
      step={3}
      summary="Ask questions about markets and your portfolio. Every number comes from the backend, with sources and timestamps."
      features={[
        "Aware of the instrument or portfolio you are viewing",
        "Answers cite retrieved data and computed metrics",
        "Labels facts, statistics, estimates and hypotheses",
        "Research aid only, never buy or sell advice",
      ]}
    />
  );
}
