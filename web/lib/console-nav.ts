import { NAV_GROUPS, PAGE_LABELS, PAGE_NAMES, type PageName } from "@/lib/constants";

export type ConsoleRoute = "dashboard" | "behavioral" | "ai" | "settings";

export const CONSOLE_NAV_ICONS: Record<PageName, string> = {
  Command: "◈",
  Intel: "◎",
  Ops: "⚡",
  Sources: "⬡",
  Cases: "◎",
  Analytics: "▤",
  ThreatSimulation: "⬡",
};

export function dashboardPageUrl(page: PageName): string {
  return page === "Command" ? "/" : `/?page=${page}`;
}

export function parseDashboardPage(raw: string | null): PageName | null {
  if (!raw) return null;
  return (PAGE_NAMES as readonly string[]).includes(raw) ? (raw as PageName) : null;
}

export function isDashboardPageActive(route: ConsoleRoute, page: PageName, current?: PageName): boolean {
  return route === "dashboard" && current === page;
}

export { NAV_GROUPS, PAGE_LABELS };
