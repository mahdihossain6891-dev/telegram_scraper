"use client";

import { useDataMode } from "@/components/mode/DataModeProvider";

type Props = {
  className?: string;
};

export function SimulationBanner({ className = "" }: Props) {
  const { mode, simulation } = useDataMode();
  const active = mode === "simulation" && simulation.simulation_active;

  if (!active) return null;

  return (
    <span
      className={`simulation-banner ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <span className="simulation-banner-icon" aria-hidden="true">
        ⚠
      </span>
      <span className="simulation-banner-text">
        <strong>SIMULATION MODE ACTIVE</strong>
        {simulation.scenario ? (
          <span className="simulation-banner-scenario">
            {" "}
            · Scenario: {simulation.scenario}
          </span>
        ) : null}
        {simulation.session_name ? (
          <span className="simulation-banner-session"> · {simulation.session_name}</span>
        ) : null}
      </span>
    </span>
  );
}
