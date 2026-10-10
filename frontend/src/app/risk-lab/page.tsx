import type { Metadata } from "next";
import { RiskLab } from "@/components/risk/risk-lab";

export const metadata: Metadata = { title: "Risk Lab" };

export default function RiskLabPage() {
  return <RiskLab />;
}
