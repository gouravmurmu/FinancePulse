import Link from "next/link";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="That page doesn't exist. It may have moved, or the link may be wrong."
      action={
        <Link href="/" className="rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent">
          Back to Markets
        </Link>
      }
    />
  );
}
