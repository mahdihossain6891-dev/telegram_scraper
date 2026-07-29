"use client";

import { useCallback, useEffect, useState } from "react";

import { useDataMode } from "@/components/mode/DataModeProvider";
import { SimulationModelSelect } from "@/components/simulation/SimulationModelSelect";
import {
  SIMULATION_MESSAGE_LIMITS,
  SIMULATION_SCENARIOS,
  formatSimulationScenariosForApi,
  loadSimulationScenarios,
  parseSimulationScenarios,
  saveSimulationScenarios,
  toggleSimulationScenario,
  type SimulationScenarioId,
} from "@/lib/simulation-settings";
import { loadSimulationModel } from "@/lib/simulation-model";

const LIMIT_STORAGE_KEY = "telegram_scraper.simulation_message_limit";

export function loadSimulationLimit(): number {
  if (typeof window === "undefined") return 24;
  try {
    const raw = window.localStorage.getItem(LIMIT_STORAGE_KEY);
    const value = Number(raw);
    return SIMULATION_MESSAGE_LIMITS.includes(value as (typeof SIMULATION_MESSAGE_LIMITS)[number])
      ? value
      : 24;
  } catch {
    return 24;
  }
}

export function saveSimulationLimit(limit: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LIMIT_STORAGE_KEY, String(limit));
  } catch {
    // ignore
  }
}

type Props = {
  compact?: boolean;
  showApplyScenario?: boolean;
  disabled?: boolean;
  onScenarioApplied?: () => void;
};

export function SimulationSettingsPanel({
  compact = false,
  showApplyScenario = true,
  disabled = false,
  onScenarioApplied,
}: Props) {
  const { simulation, refreshMode } = useDataMode();
  const [scenarios, setScenarios] = useState<SimulationScenarioId[]>(["narcotics"]);
  const [model, setModel] = useState("");
  const [limit, setLimit] = useState(24);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setModel(loadSimulationModel());
    setLimit(loadSimulationLimit());
    setScenarios(loadSimulationScenarios());
    if (simulation.scenario) {
      setScenarios(parseSimulationScenarios(simulation.scenario));
    }
  }, [simulation.scenario]);

  const applyScenario = useCallback(async () => {
    setBusy(true);
    setError("");
    setNotice("");
    const scenario = formatSimulationScenariosForApi(scenarios);
    try {
      const res = await fetch("/api/mode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "simulation",
          scenario,
          auto_start: false,
          session_name: simulation.session_name || "Console simulation",
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(body.error || body.detail || "Could not update scenario");
      }
      setNotice("Scenarios updated for the next dummy scrape.");
      onScenarioApplied?.();
      await refreshMode();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update scenario");
    } finally {
      setBusy(false);
    }
  }, [onScenarioApplied, refreshMode, scenarios, simulation.session_name]);

  function onScenarioToggle(id: SimulationScenarioId) {
    setScenarios((prev) => {
      const next = toggleSimulationScenario(prev, id);
      saveSimulationScenarios(next);
      return next;
    });
  }

  function onLimitChange(next: number) {
    setLimit(next);
    saveSimulationLimit(next);
  }

  return (
    <div className={`simulation-settings-panel${compact ? " compact" : ""}`}>
      <div className="nav-group-label">Simulator</div>
      {!compact ? (
        <p className="caption">
          Customize the AI dummy scrape — pick one or more threat scenarios, model, and batch size.
          Data is written to <code>telegram_scraper_simulation</code>.
        </p>
      ) : null}

      <div className="field-block">
        <span className="field-label">Threat scenarios</span>
        <div className="filter-chips sim-scenario-chips" role="group" aria-label="Threat scenarios">
          {SIMULATION_SCENARIOS.map((item) => {
            const active = scenarios.includes(item.id);
            return (
              <button
                key={item.id}
                type="button"
                className={active ? "filter-chip active" : "filter-chip"}
                aria-pressed={active}
                disabled={disabled || busy}
                onClick={() => onScenarioToggle(item.id)}
              >
                {item.label}
              </button>
            );
          })}
        </div>
        <p className="caption">Select multiple — dummy scrape mixes messages across chosen threats.</p>
      </div>

      <SimulationModelSelect value={model} onChange={setModel} disabled={disabled || busy} />

      <div className="field-block">
        <label className="field-label" htmlFor="sim-limit">
          Messages per run
        </label>
        <select
          id="sim-limit"
          value={limit}
          disabled={disabled || busy}
          onChange={(e) => onLimitChange(Number(e.target.value))}
        >
          {SIMULATION_MESSAGE_LIMITS.map((value) => (
            <option key={value} value={value}>
              {value} messages
            </option>
          ))}
        </select>
      </div>

      {showApplyScenario ? (
        <button
          type="button"
          className="btn block"
          disabled={disabled || busy}
          onClick={() => void applyScenario()}
        >
          {busy ? "Applying…" : "Apply scenarios"}
        </button>
      ) : null}

      {error ? <p className="caption error-text">{error}</p> : null}
      {notice ? <p className="caption success-text">{notice}</p> : null}
    </div>
  );
}
