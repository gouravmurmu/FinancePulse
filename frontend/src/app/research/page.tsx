import type { Metadata } from "next";
import { ResearchBrowser } from "@/components/research/research-browser";

export const metadata: Metadata = { title: "Research" };

export default function ResearchPage() {
  return <ResearchBrowser />;
}
