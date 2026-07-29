"use client";

import { dataSourceLabel, pageLabel, type PageName } from "@/lib/constants";

export type AppNavbarProps = {
  page: PageName;
  source: string;
  autoRefresh: boolean;
  refreshSeconds: number;
  collection: { channels: number; groups: number; privateDms: number };
  intelWindow: string;
  riskPosture: string;
  onManualRefresh?: () => void;
};

function systemStatusLabel(source: string): { label: string; className: string } {
  if (source === "mongodb") {
    return { label: "Live · Connected", className: "system-status live" };
  }
  return { label: dataSourceLabel(source), className: "system-status idle" };
}

export function AppNavbar({
  page,
  source,
  autoRefresh,
  refreshSeconds,
  collection,
  intelWindow,
  riskPosture,
  onManualRefresh,
}: AppNavbarProps) {
  const system = systemStatusLabel(source);

  return (
    <header className="app-navbar console-top-header">
      <span className="app-navbar-title">
        <h1>{pageLabel(page)}</h1>
        <span className="source-badge">{dataSourceLabel(source)}</span>
      </span>
      <span className="app-navbar-meta">
        <span className={`status-pill ${system.className}`} title="System status">
          <span className="system-status-dot" aria-hidden="true" />
          {system.label}
        </span>
        <span className={`status-pill ${autoRefresh ? "live" : ""}`}>
          {autoRefresh ? `Refresh · ${refreshSeconds}s` : "Paused"}
        </span>
        <span className="status-item">
          <em>Collection</em>
          {collection.channels} ch · {collection.groups} grp · {collection.privateDms} DM
        </span>
        <span className="status-item">
          <em>Intel</em>
          {intelWindow}
        </span>
        <span className="status-item">
          <em>Risk</em>
          {riskPosture}
        </span>
        <button
          type="button"
          className="icon-btn"
          aria-label="Refresh"
          onClick={() => onManualRefresh?.()}
        >
          ↻
        </button>
      </span>
    </header>
  );
}
