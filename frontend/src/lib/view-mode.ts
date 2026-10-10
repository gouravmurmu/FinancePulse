"use client";

import { useCallback, useSyncExternalStore } from "react";

/** Simple shows the key numbers with explanations; Pro adds the full tables,
 * extra indicators and model diagnostics. Remembered per browser. */
export type ViewMode = "simple" | "pro";

const KEY = "marketpulse.view";
const EVENT = "marketpulse:view";

function read(): ViewMode {
  try {
    return localStorage.getItem(KEY) === "pro" ? "pro" : "simple";
  } catch {
    return "simple";
  }
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useViewMode(): [ViewMode, (m: ViewMode) => void] {
  const mode = useSyncExternalStore(subscribe, read, () => "simple" as ViewMode);
  const set = useCallback((m: ViewMode) => {
    try {
      localStorage.setItem(KEY, m);
    } catch {
      // Private mode: the choice lasts for this page only.
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [mode, set];
}

export function useIsPro(): boolean {
  return useViewMode()[0] === "pro";
}
