"use client";

import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

export type ConsoleMode = "live";

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

const LIVE_STATE: SimulationState = {
  mode: "live",
  simulation_active: false,
  scenario: null,
  session_id: null,
  session_name: null,
};

const DataModeContext = createContext<DataModeContextValue | null>(null);

const noop = async () => {};

export function DataModeProvider({ children }: { children: ReactNode }) {
  const value = useMemo<DataModeContextValue>(
    () => ({
      mode: "live",
      simulation: LIVE_STATE,
      busy: false,
      error: null,
      refreshMode: noop,
      setLiveMode: noop,
      setSimulationMode: noop,
      endSimulation: noop,
    }),
    [],
  );

  return <DataModeContext.Provider value={value}>{children}</DataModeContext.Provider>;
}

export function useDataMode(): DataModeContextValue {
  const ctx = useContext(DataModeContext);
  if (!ctx) {
    throw new Error("useDataMode must be used within DataModeProvider");
  }
  return ctx;
}
