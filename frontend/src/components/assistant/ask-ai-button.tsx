"use client";

import { Bot, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AssistantChat } from "./chat";

/** Header button that opens the assistant in a side panel, aware of the current page.
 * The panel is portalled to <body> because the blurred header would otherwise
 * become the containing block of a fixed element. */
export function AskAiButton() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (pathname.startsWith("/assistant")) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-controls="ask-ai-panel"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-sm hover:border-accent hover:text-accent"
      >
        <Bot size={16} aria-hidden="true" />
        <span className="hidden sm:inline">Ask AI</span>
        <span className="sr-only sm:hidden">Ask the AI assistant</span>
      </button>
      {open
        ? createPortal(
            <div className="fixed inset-0 z-40">
              <button
                type="button"
                aria-label="Close assistant"
                tabIndex={-1}
                onClick={() => setOpen(false)}
                className="absolute inset-0 bg-black/30"
              />
              <div
                id="ask-ai-panel"
                ref={panelRef}
                tabIndex={-1}
                role="dialog"
                aria-modal="true"
                aria-label="AI assistant"
                className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col gap-3 border-l border-border bg-bg p-4 shadow-xl outline-none"
              >
                <div className="flex items-center justify-between">
                  <h2 className="flex items-center gap-2 font-semibold">
                    <Bot size={18} aria-hidden="true" className="text-accent" /> Ask AI
                  </h2>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    aria-label="Close assistant"
                    className="rounded-lg p-1.5 text-muted hover:text-text"
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </div>
                <AssistantChat compact />
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
