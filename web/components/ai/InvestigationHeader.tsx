"use client";

import type { AiHealth, Confidence } from "./types";
import { AiModelPicker } from "./AiModelPicker";
import { ModeToggle } from "@/components/mode/ModeToggle";
import { confidenceClass, formatLatency } from "./utils";

type Props = {
  health: AiHealth | null;
  ready: boolean;
  modelLabel: string;
  providerLabel: string;
  providerStatus?: string | null;
  latencyMs: number | null;
  confidence?: Confidence;
  onRefresh: () => void;
  onOpenSettings: () => void;
};

function statusText(status?: string | null, ready?: boolean): string {
  if (status === "healthy") return "Healthy";
  if (status === "slow") return "Slow";
  if (status === "offline") return "Offline";
  return ready ? "Connected" : "Offline";
}

export function InvestigationHeader({
  health,
  ready,
  modelLabel,
  providerLabel,
  providerStatus,
  latencyMs,
  confidence,
  onRefresh,
  onOpenSettings,
}: Props) {
  const status = statusText(providerStatus, ready);
  const statusClass =
    providerStatus === "healthy" || (ready && !providerStatus)
      ? "live ok"
      : providerStatus === "slow"
        ? "idle warn"
        : "idle warn";

  return (
    <header className="ai-header ba-header console-top-header">
      <div>
        <h1>Sébastien</h1>
        <p className="ai-tagline">AI Investigation Copilot</p>
        <div className="ai-header-meta" aria-label="Active model context">
          <span>
            Provider: <strong>{providerLabel || "—"}</strong>
          </span>
          <span>
            Model: <strong>{modelLabel || "—"}</strong>
          </span>
          <span>
            Status: <strong>{status}</strong>
          </span>
        </div>
        <AiModelPicker compact />
        <ModeToggle />
      </div>
      <div className="ai-status-row" aria-label="Service status">
        <span className={`status-pill ai-status-chip system-status ${statusClass}`}>
          <span className="system-status-dot" aria-hidden="true" />
          {status}
        </span>
        <span className="status-pill ai-status-chip muted" title="Current AI model">
          {modelLabel}
        </span>
        <span className="status-pill ai-status-chip muted" title="Last response time">
          {formatLatency(latencyMs)}
        </span>
        {confidence ? (
          <span className={confidenceClass(confidence)}>Confidence: {confidence}</span>
        ) : null}
        <button type="button" className="btn ai-btn-ghost ai-status-refresh" onClick={onRefresh}>
          Refresh
        </button>
        <button
          type="button"
          className="btn primary ai-cc-open-btn"
          onClick={onOpenSettings}
          title="Open AI Control Center"
        >
          Settings
        </button>
        {health?.vector_backend ? (
          <span className="caption ai-status-backend">{health.vector_backend}</span>
        ) : null}
      </div>
    </header>
  );
}
