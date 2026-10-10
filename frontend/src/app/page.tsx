import { SystemStatus } from "@/components/system/system-status";
import { Card } from "@/components/ui/card";

export default function MarketsPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold">Markets</h1>
        <p className="mt-1 max-w-prose text-muted">
          Global and Indian indices, stocks, crypto, gold and silver in one view. Market data
          arrives in the next build step; this page currently shows the health of each tier.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <SystemStatus />
        </div>
        <Card className="lg:col-span-7">
          <p className="label">Coming next</p>
          <ul className="mt-3 grid gap-2 text-muted sm:grid-cols-2">
            <li>Index cards with latest price and change</li>
            <li>Stock, crypto, gold and silver snapshots</li>
            <li>Performance comparison, normalized to 100</li>
            <li>Top gainers and losers</li>
            <li>Market open/closed badges per exchange</li>
            <li>Freshness on every number</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
