"use client";

import { useEffect, useRef, useState } from "react";
import { SkeletonCard } from "./states";

/** Renders its children once they come near the viewport. Keeps the first
 * paint of long pages light; the placeholder keeps the layout stable. */
export function Deferred({
  children,
  lines = 4,
  minHeight = 240,
}: {
  children: React.ReactNode;
  lines?: number;
  minHeight?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || show) return;
    if (typeof IntersectionObserver === "undefined") {
      setShow(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShow(true);
          io.disconnect();
        }
      },
      { rootMargin: "400px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [show]);

  if (show) return <>{children}</>;
  return (
    <div ref={ref} style={{ minHeight }}>
      <SkeletonCard lines={lines} />
    </div>
  );
}
