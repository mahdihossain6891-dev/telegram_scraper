"use client";

import { useCallback, useEffect, useState } from "react";

import { DashboardApp } from "@/components/DashboardApp";
import type { ExportPayload } from "@/lib/types";

type ApiResponse = {
  source: string;
  payload: ExportPayload;
  error?: string;
};

export default function HomePage() {
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
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }
    const timer = window.setInterval(loadData, refreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, refreshSeconds, loadData]);

  if (error) {
    return (
      <main className="standalone-main">
        <div className="hero">
          <h1>Telegram Intelligence Dashboard</h1>
        </div>
        <div className="error">{error}</div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="standalone-main">
        <div className="hero">
          <h1>Telegram Intelligence Dashboard</h1>
          <p>Loading export data...</p>
        </div>
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
