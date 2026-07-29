"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ScrapeJobStatus = {
  status: "idle" | "running" | "completed" | "failed";
  channels_total: number;
  channels_scanned: number;
  messages_analyzed: number;
  threats_detected: number;
  current_channel: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_run_at: string | null;
  error: string | null;
  scope: string | null;
  limit_per_chat: number | null;
};

const IDLE_STATUS: ScrapeJobStatus = {
  status: "idle",
  channels_total: 0,
  channels_scanned: 0,
  messages_analyzed: 0,
  threats_detected: 0,
  current_channel: null,
  started_at: null,
  finished_at: null,
  last_run_at: null,
  error: null,
  scope: null,
  limit_per_chat: null,
};

async function fetchScrapeStatus(): Promise<ScrapeJobStatus> {
  const res = await fetch("/api/scrape/status", { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Unable to load scrape status");
  }
  return (await res.json()) as ScrapeJobStatus;
}

async function startScrapeJob(): Promise<ScrapeJobStatus> {
  const res = await fetch("/api/scrape/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof body?.error === "string"
          ? body.error
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join("; ") ||
              "Failed to start scrape"
            : "Failed to start scrape";
    throw new Error(message);
  }
  return (body.status as ScrapeJobStatus) || (body as ScrapeJobStatus);
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statusLabel(status: ScrapeJobStatus["status"]): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return "Idle";
  }
}

type Props = {
  onScrapeComplete?: () => void;
};

export function ScrapeControl({ onScrapeComplete }: Props) {
  const [status, setStatus] = useState<ScrapeJobStatus>(IDLE_STATUS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await fetchScrapeStatus();
      setStatus(next);
      return next;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (status.status !== "running") {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, 1500);
    return () => window.clearInterval(timer);
  }, [status.status, refresh]);

  const completedRef = useRef<string | null>(null);
  const completedAt = status.finished_at;
  useEffect(() => {
    if (
      (status.status === "completed" || status.status === "failed") &&
      completedAt &&
      completedRef.current !== completedAt
    ) {
      completedRef.current = completedAt;
      if (status.status === "completed") {
        onScrapeComplete?.();
      }
    }
  }, [status.status, completedAt, onScrapeComplete]);

  async function handleRun() {
    setBusy(true);
    setError("");
    try {
      const current = await refresh();
      if (current?.status === "running") {
        setError("A scrape job is already running — wait for it to finish.");
        return;
      }
      const next = await startScrapeJob();
      setStatus(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scrape failed to start");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const running = status.status === "running" || busy;
  const pillClass =
    status.status === "running"
      ? "live"
      : status.status === "failed"
        ? "danger"
        : status.status === "completed"
          ? "success"
          : "";

  return (
    <section className="scrape-control glass-card" aria-label="Scrape controls">
      <div className="scrape-control-head">
        <div className="scrape-control-title">
          <h2>Collection</h2>
          <span className={`status-pill ${pillClass}`}>{statusLabel(status.status)}</span>
        </div>
        <button
          type="button"
          className="btn primary scrape-run-btn"
          onClick={() => void handleRun()}
          disabled={running}
        >
          {running ? "Scraping…" : "▶ Run Scrape"}
        </button>
      </div>

      {error ? <div className="error compact">{error}</div> : null}
      {status.error ? <div className="error compact">{status.error}</div> : null}

      <div className="scrape-metrics">
        <div className="scrape-metric">
          <span className="metric-label">Channels</span>
          <strong>
            {status.channels_scanned}
            {status.channels_total ? ` / ${status.channels_total}` : ""}
          </strong>
        </div>
        <div className="scrape-metric">
          <span className="metric-label">Messages analyzed</span>
          <strong>{status.messages_analyzed}</strong>
        </div>
        <div className="scrape-metric">
          <span className="metric-label">Threats detected</span>
          <strong className="threat-count">{status.threats_detected}</strong>
        </div>
        <div className="scrape-metric">
          <span className="metric-label">Last run</span>
          <strong className="caption mono">{formatTimestamp(status.last_run_at)}</strong>
        </div>
      </div>

      {status.current_channel ? (
        <p className="caption scrape-current">
          Scanning <strong>{status.current_channel}</strong>
          {status.scope ? ` · scope ${status.scope}` : ""}
        </p>
      ) : (
        <p className="caption scrape-note">
          Keyword-filtered scrape across monitored channels/groups only (narcotics, weapons,
          trafficking, illegal activity terms). Private DMs excluded unless configured.
        </p>
      )}
    </section>
  );
}
