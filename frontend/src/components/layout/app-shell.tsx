"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { NAV_ITEMS, isActive } from "./nav";
import { CommandSearch } from "@/components/search/command-search";
import { AccountMenu } from "@/components/auth/account-menu";
import { useAlertEvents } from "@/lib/alerts";
import { ThemeToggle } from "./theme-toggle";
import { AskAiButton } from "@/components/assistant/ask-ai-button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const unread = useAlertEvents().data?.unread ?? 0;
  const badge = (href: string) =>
    href === "/alerts" && unread > 0 ? (
      <span
        className="absolute -right-1 -top-1 size-2 rounded-full bg-accent"
        aria-label={`${unread} unread alerts`}
      />
    ) : null;

  return (
    <div className="flex min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface/60 py-4 md:flex",
          collapsed ? "w-16 px-2" : "w-56 px-3",
        )}
      >
        <Link href="/" className="mb-6 flex items-center gap-2 px-2 font-semibold">
          <span aria-hidden="true" className="inline-block size-6 rounded-md bg-accent/90" />
          {collapsed ? <span className="sr-only">MarketPulse</span> : <span>MarketPulse</span>}
        </Link>
        <nav aria-label="Primary" className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                title={collapsed ? label : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-2 py-2 text-muted hover:bg-surface-raised hover:text-text",
                  active && "bg-surface-raised font-medium text-text",
                )}
              >
                <span className="relative">
                  <Icon
                    size={18}
                    aria-hidden="true"
                    className={active ? "text-accent" : undefined}
                  />
                  {badge(href)}
                </span>
                {collapsed ? <span className="sr-only">{label}</span> : label}
              </Link>
            );
          })}
        </nav>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex items-center gap-3 rounded-lg px-2 py-2 text-muted hover:text-text"
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
          {collapsed ? null : <span className="text-sm">Collapse</span>}
        </button>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur md:px-6">
          <span className="font-semibold md:hidden">MarketPulse</span>
          <div className="flex flex-1 justify-center md:justify-start">
            <CommandSearch />
          </div>
          <AskAiButton />
          <ThemeToggle />
          <AccountMenu />
        </header>

        <main
          id="main"
          className="mx-auto w-full max-w-[1440px] flex-1 px-4 pb-24 pt-6 md:px-6 md:pb-10"
        >
          {children}
        </main>

        <footer className="hidden border-t border-border px-6 py-4 text-xs text-subtle md:block">
          MarketPulse is a research tool, not investment advice. Prices may be delayed or end of
          day; every figure shows its source and as-of time.
        </footer>
      </div>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-border bg-surface md:hidden"
      >
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-col items-center gap-0.5 py-2 text-[11px] text-muted",
                active && "text-accent",
              )}
            >
              <span className="relative">
                <Icon size={18} aria-hidden="true" />
                {badge(href)}
              </span>
              <span className="truncate">{label.replace("AI ", "")}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
