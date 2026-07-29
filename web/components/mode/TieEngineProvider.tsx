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

export type TieEngineState = {
  enabled: boolean;
  analyser: "tie" | "console_builtin" | string;
  description: string;
  updated_at?: string | null;
};

type TieEngineContextValue = {
  enabled: boolean;
  analyser: string;
  description: string;
  busy: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setEnabled: (enabled: boolean) => Promise<void>;
};

const DEFAULT: TieEngineState = {
  enabled: false,
  analyser: "console_builtin",
  description: "Threat Console built-in scrape analyser",
  updated_at: null,
};

const TieEngineContext = createContext<TieEngineContextValue | null>(null);

async function fetchMode(): Promise<TieEngineState> {
  const res = await fetch("/api/tie-engine", { cache: "no-store" });
  if (!res.ok) return DEFAULT;
  const body = (await res.json()) as TieEngineState;
  return {
    enabled: Boolean(body.enabled),
    analyser: body.analyser || (body.enabled ? "tie" : "console_builtin"),
    description:
      body.description ||
      (body.enabled
        ? "TIE processes scrape intelligence"
        : "Threat Console built-in scrape analyser"),
    updated_at: body.updated_at ?? null,
  };
}

export function TieEngineProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<TieEngineState>(DEFAULT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchMode();
      setState(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load TIE mode");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setEnabled = useCallback(async (enabled: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/tie-engine", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body?.error || body?.detail || "Failed to update TIE mode");
      }
      setState({
        enabled: Boolean(body.enabled),
        analyser: body.analyser || (enabled ? "tie" : "console_builtin"),
        description:
          body.description ||
          (enabled
            ? "TIE processes scrape intelligence"
            : "Threat Console built-in scrape analyser"),
        updated_at: body.updated_at ?? null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update TIE mode");
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      enabled: state.enabled,
      analyser: state.analyser,
      description: state.description,
      busy,
      error,
      refresh,
      setEnabled,
    }),
    [state, busy, error, refresh, setEnabled],
  );

  return <TieEngineContext.Provider value={value}>{children}</TieEngineContext.Provider>;
}

export function useTieEngine(): TieEngineContextValue {
  const ctx = useContext(TieEngineContext);
  if (!ctx) {
    throw new Error("useTieEngine must be used within TieEngineProvider");
  }
  return ctx;
}
