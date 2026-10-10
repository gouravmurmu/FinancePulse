import { Bell, Bot, Briefcase, LineChart, Search, ShieldAlert, type LucideIcon } from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Markets", icon: LineChart },
  { href: "/research", label: "Research", icon: Search },
  { href: "/risk-lab", label: "Risk Lab", icon: ShieldAlert },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/assistant", label: "AI Assistant", icon: Bot },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
