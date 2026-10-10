"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "./auth-provider";

export function AccountMenu() {
  const { ready, configured, session, email, signOut } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)
      )
        setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (!ready || !configured) return null;
  if (!session) {
    return (
      <Link
        href={`/sign-in?next=${encodeURIComponent(pathname)}`}
        className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:border-accent"
      >
        Sign in
      </Link>
    );
  }
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account"
        onClick={() => setOpen((o) => !o)}
        className="flex size-9 items-center justify-center rounded-full border border-border bg-surface-raised text-muted hover:text-text"
      >
        <UserRound size={18} aria-hidden="true" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-11 z-40 w-64 rounded-card border border-border bg-surface-raised p-2 shadow-card"
        >
          <p className="truncate px-2 py-1.5 text-sm text-muted" title={email ?? undefined}>
            {email}
          </p>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              void signOut();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface"
          >
            <LogOut size={16} aria-hidden="true" /> Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
