"use client";

import Link from "next/link";

import {
  CONSOLE_NAV_ICONS,
  NAV_GROUPS,
  PAGE_LABELS,
  dashboardPageUrl,
  isDashboardPageActive,
  type ConsoleRoute,
} from "@/lib/console-nav";
import type { PageName } from "@/lib/constants";

type Props = {
  active: ConsoleRoute;
  dashboardPage?: PageName;
  className?: string;
};

export function ConsoleJumpNav({ active, dashboardPage, className = "" }: Props) {
  return (
    <aside
      className={`console-jump-nav sidebar soc-sidebar${className ? ` ${className}` : ""}`}
      aria-label="Platform navigation"
    >
      <div className="sidebar-brand">
        <Link href="/" className="brand-mark console-jump-brand">
          <span className="brand-icon" aria-hidden="true">
            TC
          </span>
          <div>
            <h2>Threat Console</h2>
            <p>SOC · Telegram OSINT</p>
          </div>
        </Link>
      </div>

      <nav className="sidebar-nav" aria-label="Jump to page">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="nav-group">
            <div className="nav-group-label">{group.label}</div>
            {group.pages.map((name) => {
              const isActive = isDashboardPageActive(active, name, dashboardPage);
              return (
                <Link
                  key={name}
                  href={dashboardPageUrl(name)}
                  className={isActive ? "nav-btn active" : "nav-btn"}
                  aria-current={isActive ? "page" : undefined}
                  title={PAGE_LABELS[name]}
                >
                  <span className="nav-icon" aria-hidden="true">
                    {CONSOLE_NAV_ICONS[name]}
                  </span>
                  <span className="nav-label">{PAGE_LABELS[name]}</span>
                </Link>
              );
            })}
          </div>
        ))}
        <div className="nav-group">
          <div className="nav-group-label">Intel+</div>
          <Link
            href="/behavioral-analytics"
            className={active === "behavioral" ? "nav-btn active ba-nav-link" : "nav-btn ba-nav-link"}
            aria-current={active === "behavioral" ? "page" : undefined}
            title="Behavioral Analytics"
          >
            <span className="nav-icon" aria-hidden="true">
              ◉
            </span>
            <span className="nav-label">Behavioral Analytics</span>
          </Link>
          <Link
            href="/ai"
            className={active === "ai" ? "nav-btn active ba-nav-link ai-nav-link" : "nav-btn ba-nav-link ai-nav-link"}
            aria-current={active === "ai" ? "page" : undefined}
            title="Sébastien"
          >
            <span className="nav-icon" aria-hidden="true">
              ✦
            </span>
            <span className="nav-label-stack">
              <span className="ai-nav-title">Sébastien</span>
              <span className="ai-nav-sub">AI Copilot</span>
            </span>
          </Link>
        </div>
      </nav>

      <div className="sidebar-footer console-jump-footer">
        <Link
          href="/settings"
          className={active === "settings" ? "nav-btn settings-toggle active" : "nav-btn settings-toggle"}
          aria-current={active === "settings" ? "page" : undefined}
          title="API keys & configuration"
        >
          <span className="nav-icon" aria-hidden="true">
            ⚙
          </span>
          <span className="nav-label">Settings</span>
        </Link>
      </div>
    </aside>
  );
}
