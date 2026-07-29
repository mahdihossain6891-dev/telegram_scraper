"use client";

import { dataSourceLabel, pageLabel, type PageName } from "@/lib/constants";
import { formatSimulationScenarioLabels } from "@/lib/simulation-settings";
import { ModeToggle } from "@/components/mode/ModeToggle";
import { useDataMode } from "@/components/mode/DataModeProvider";

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

function systemStatusLabel(
  mode: string,
  simulationActive: boolean,
  source: string,
): { label: string; className: string } {
  if (mode === "simulation" && simulationActive) {
    return { label: "Simulation", className: "system-status sim" };
  }
  if (source === "mongodb") {
    return { label: "Live · Connected", className: "system-status live" };
  }
  if (source === "simulation") {
    return { label: "Simulation data", className: "system-status sim" };
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
  const { mode, simulation } = useDataMode();
  const system = systemStatusLabel(mode, simulation.simulation_active, source);
  const isSim = mode === "simulation" && simulation.simulation_active;

  return (
    <header className="app-navbar console-top-header">
      <span className="app-navbar-title">
        <h1>{pageLabel(page)}</h1>
        <span className="source-badge">{dataSourceLabel(source)}</span>
      </span>
      <span className="app-navbar-meta">
        {page === "Command" ? <ModeToggle /> : null}
        <span className={`status-pill ${system.className}`} title="System status">
          <span className="system-status-dot" aria-hidden="true" />
          {system.label}
        </span>
        {isSim && simulation.scenario ? (
          <span className="status-item scenario-pill" title="Active simulation scenarios">
            <em>Scenarios</em>
            {formatSimulationScenarioLabels(simulation.scenario)}
          </span>
        ) : null}
        <span className={`status-pill ${autoRefresh || isSim ? "live" : ""}`}>
          {isSim ? "Sim feed · 5s" : autoRefresh ? `Refresh · ${refreshSeconds}s` : "Paused"}
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
