"use client";

import { useDataMode } from "@/components/mode/DataModeProvider";
import {
  formatSimulationScenariosForApi,
  loadSimulationScenarios,
} from "@/lib/simulation-settings";

export function ModeToggle() {
  const { mode, simulation, busy, error, setLiveMode, setSimulationMode, endSimulation } =
    useDataMode();
  const isSim = mode === "simulation" && simulation.simulation_active;

  return (
    <>
      <span className="mode-toggle" role="group" aria-label="Console data mode">
        <button
          type="button"
          className={`mode-toggle-btn ${!isSim ? "active" : ""}`}
          disabled={busy}
          onClick={() => void setLiveMode()}
          title="Use live MongoDB and Telegram data"
        >
          Live
        </button>
        <button
          type="button"
          className={`mode-toggle-btn ${isSim ? "active sim" : ""}`}
          disabled={busy}
          onClick={() => {
            if (isSim) {
              void endSimulation();
            } else {
              void setSimulationMode({
                scenario: formatSimulationScenariosForApi(loadSimulationScenarios()),
              });
            }
          }}
          title={
            isSim
              ? "End simulation and return to live data"
              : "Replace console with synthetic simulation data"
          }
        >
          Simulation
        </button>
      </span>
      {error ? (
        <span className="mode-toggle-error caption" role="alert" title={error}>
          Mode switch failed
        </span>
      ) : null}
    </>
  );
}
