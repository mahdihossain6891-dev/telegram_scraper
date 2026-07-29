"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ConsoleMode = "live" | "simulation";

export type SimulationState = {
  mode: ConsoleMode;
  simulation_active: boolean;
  scenario: string | null;
  session_id: string | null;
  session_name: string | null;
};

type DataModeContextValue = {
  mode: ConsoleMode;
  simulation: SimulationState;
  busy: boolean;
  error: string | null;
  refreshMode: () => Promise<void>;
  setLiveMode: () => Promise<void>;
  setSimulationMode: (opts?: { scenario?: string; sessionName?: string }) => Promise<void>;
  endSimulation: () => Promise<void>;
};

const DEFAULT_STATE: SimulationState = {
  mode: "live",
  simulation_active: false,
  scenario: null,
  session_id: null,
  session_name: null,
};

const DataModeContext = createContext<DataModeContextValue | null>(null);

async function fetchMode(): Promise<SimulationState> {
  const res = await fetch("/api/mode", { cache: "no-store" });
  if (!res.ok) {
    return DEFAULT_STATE;
  }
  return (await res.json()) as SimulationState;
}

export function DataModeProvider({ children }: { children: ReactNode }) {
  const [simulation, setSimulation] = useState<SimulationState>(DEFAULT_STATE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshMode = useCallback(async () => {
    const state = await fetchMode();
    setSimulation(state);
  }, []);

  useEffect(() => {
    void refreshMode().then(async () => {
      const res = await fetch("/api/mode", { cache: "no-store" });
      if (res.status === 404) {
        setError(
          "Simulation mode API not found. Restart the FastAPI server (dashboard.bat) so /api/mode is available.",
        );
      }
    });
  }, [refreshMode]);

  const setLiveMode = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/mode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "live" }),
      });
      if (res.ok) {
        setSimulation((await res.json()) as SimulationState);
      } else {
        const body = (await res.json().catch(() => ({}))) as { error?: string; detail?: string };
        setError(body.error || body.detail || `Could not switch to live mode (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach mode API");
    } finally {
      setBusy(false);
    }
  }, []);

  const setSimulationMode = useCallback(
    async (opts?: { scenario?: string; sessionName?: string }) => {
      setBusy(true);
      setError(null);
      try {
        const res = await fetch("/api/mode", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: "simulation",
            scenario: opts?.scenario || "narcotics",
            session_name: opts?.sessionName || "Console simulation",
            auto_start: false,
          }),
        });
        if (res.ok) {
          setSimulation((await res.json()) as SimulationState);
        } else {
          const body = (await res.json().catch(() => ({}))) as { error?: string; detail?: string };
          setError(
            body.error ||
              body.detail ||
              (res.status === 404
                ? "Simulation mode API not found — restart the FastAPI server (dashboard.bat)."
                : `Could not enable simulation (${res.status})`),
          );
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not reach mode API");
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const endSimulation = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/mode/end", { method: "POST" });
      if (res.ok) {
        setSimulation((await res.json()) as SimulationState);
      } else {
        const body = (await res.json().catch(() => ({}))) as { error?: string; detail?: string };
        setError(body.error || body.detail || `Could not end simulation (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach mode API");
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo<DataModeContextValue>(
    () => ({
      mode: simulation.mode,
      simulation,
      busy,
      error,
      refreshMode,
      setLiveMode,
      setSimulationMode,
      endSimulation,
    }),
    [simulation, busy, error, refreshMode, setLiveMode, setSimulationMode, endSimulation],
  );

  return (
    <DataModeContext.Provider value={value}>{children}</DataModeContext.Provider>
  );
}

export function useDataMode(): DataModeContextValue {
  const ctx = useContext(DataModeContext);
  if (!ctx) {
    throw new Error("useDataMode must be used within DataModeProvider");
  }
  return ctx;
}
