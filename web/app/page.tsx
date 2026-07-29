"use client";

import { useCallback, useEffect, useState } from "react";

import { DashboardApp } from "@/components/DashboardApp";
import { useDataMode } from "@/components/mode/DataModeProvider";
import type { ExportPayload } from "@/lib/types";

type ApiResponse = {
  source: string;
  payload: ExportPayload;
  mode?: string;
  simulation_state?: {
    simulation_active?: boolean;
    scenario?: string | null;
    session_id?: string | null;
  };
  error?: string;
};

export default function HomePage() {
  const { mode, simulation } = useDataMode();
  const [data, setData] = useState<ApiResponse | null>(null);
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState(30);
  const [lastFetchedAt, setLastFetchedAt] = useState("");

  const loadData = useCallback(async () => {
    try {
      const response = await fetch("/api/data", { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) {
        setError(body.error || "Failed to load export data.");
        return;
      }
      setError("");
      setData(body as ApiResponse);
      setLastFetchedAt(new Date().toLocaleString());
    } catch {
      setError("Could not load dashboard data.");
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, mode, simulation.session_id, simulation.simulation_active]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    const intervalSeconds = mode === "simulation" ? 5 : refreshSeconds;
    const timer = window.setInterval(loadData, intervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, refreshSeconds, loadData, mode]);

  if (error) {
    return (
      <main className="standalone-main">
        <span className="page-header">
          <h1>Threat Console</h1>
          <p>Could not load dashboard data.</p>
        </span>
        <span className="error">{error}</span>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="standalone-main">
        <span className="page-header">
          <h1>Threat Console</h1>
          <p>Loading command posture…</p>
        </span>
        <span className="metric-grid">
          <span className="metric-card">
            <span className="metric-label">Preparing</span>
            <span className="metric-value">…</span>
          </span>
          <span className="metric-card">
            <span className="metric-label">Charts</span>
            <span className="metric-value">…</span>
          </span>
          <span className="metric-card">
            <span className="metric-label">Tables</span>
            <span className="metric-value">…</span>
          </span>
          <span className="metric-card">
            <span className="metric-label">Risk</span>
            <span className="metric-value">…</span>
          </span>
        </span>
      </main>
    );
  }

  return (
    <DashboardApp
      source={data.source}
      payload={data.payload}
      autoRefresh={autoRefresh}
      refreshSeconds={refreshSeconds}
      lastFetchedAt={lastFetchedAt}
      onAutoRefreshChange={setAutoRefresh}
      onRefreshSecondsChange={setRefreshSeconds}
      onManualRefresh={loadData}
    />
  );
}
