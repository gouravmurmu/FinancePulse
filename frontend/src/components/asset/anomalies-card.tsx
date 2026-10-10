"use client";

import Link from "next/link";
import { BellPlus } from "lucide-react";
import { AnomalyList } from "@/components/alerts/anomaly-list";
import { Card, CardHeader } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { QueryState } from "@/components/ui/query-state";
import { useAnomalies } from "@/lib/alerts";

/** The past year's statistical flags for one asset, with a shortcut to set an alert. */
export function AnomaliesCard({ id }: { id: string }) {
  const q = useAnomalies(id, 365);
  return (
    <Card>
      <CardHeader
        title="Unusual activity"
        subtitle="Statistical flags, past 12 months"
        action={
          <InfoTip label="About these flags">
            Days when this asset&apos;s move, volume, volatility or correlation with its benchmark
            was far outside its own previous year (robust z-score). They describe what happened and
            are not predictions or trading signals.
          </InfoTip>
        }
      />
      <QueryState query={q} skeletonLines={3}>
        {(list) => (
          <AnomalyList items={list.slice(0, 8)} empty="Nothing unusual flagged in the past year." />
        )}
      </QueryState>
      <Link
        href={`/alerts?instrument=${encodeURIComponent(id)}`}
        className="mt-3 inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
      >
        <BellPlus size={15} aria-hidden="true" /> Alert me about this asset
      </Link>
    </Card>
  );
}
