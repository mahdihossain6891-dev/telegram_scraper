"use client";

import { useEffect, useState } from "react";

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

  useEffect(() => {
    async function loadData() {
      try {
        const response = await fetch("/api/data");
        const body = await response.json();
        if (!response.ok) {
          setError(body.error || "Failed to load export data.");
          return;
        }
        setData(body as ApiResponse);
      } catch {
        setError("Could not load dashboard data.");
      }
    }

    loadData();
  }, []);

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

  return <DashboardApp source={data.source} payload={data.payload} />;
}
