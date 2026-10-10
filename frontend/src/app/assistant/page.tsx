import type { Metadata } from "next";
import { AssistantChat } from "@/components/assistant/chat";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "AI Assistant" };

export default function AssistantPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <header>
        <h1 className="text-xl font-semibold">AI Assistant</h1>
        <p className="mt-1 text-sm text-muted">
          Ask about markets and your portfolio. The assistant looks up prices, risk, filings, news
          and forecasts in MarketPulse, labels each statement as a fact, a computed figure, a model
          estimate or its own reading, and never tells you what to buy or sell.
        </p>
      </header>
      <Card className="flex min-h-[60dvh] flex-col">
        <AssistantChat />
      </Card>
    </div>
  );
}
