"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { StatCard } from "@/components/ui";
import { useTieEngine } from "@/components/mode/TieEngineProvider";
import {
  canConfigureTieAi,
  canViewTieOpsDetail,
  getTieConsoleRole,
  type TieConsoleRole,
} from "@/lib/tie-role";
import type { TieAiConfig, TieSnapshot } from "@/lib/tie-types";
import {
  fetchTieAiConfig,
  fetchTieAiModels,
  fetchTieProcessStatus,
  loadTieSnapshot,
  startTieProcess,
  stopTieProcess,
  updateTieAiConfig,
  type TieProcessStatus,
} from "@/services/tieService";

const DEFAULT_REFRESH_SEC = 30;

function formatNumber(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat().format(n);
}

/** Coerce API category fields that may be `{name, confidence}` objects. */
function formatLabel(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const name = obj.name ?? obj.category ?? obj.label ?? obj.id;
    if (name != null && (typeof name === "string" || typeof name === "number")) {
      return String(name);
    }
  }
  return "—";
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const sec = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function statusDotClass(status: string | undefined): string {
  const s = (status || "").toLowerCase();
  if (s.includes("operational") || s === "healthy" || s === "online" || s === "connected") {
    return "tie-dot ok";
  }
  if (s === "processing") return "tie-dot processing";
  if (s === "warning" || s === "degraded") return "tie-dot warn";
  if (s === "failed" || s === "offline" || s === "error") return "tie-dot fail";
  return "tie-dot warn";
}

type ThreatIntelligencePageProps = {
  role?: TieConsoleRole;
  refreshSeconds?: number;
};

export function ThreatIntelligencePage({
  role: roleProp,
  refreshSeconds = DEFAULT_REFRESH_SEC,
}: ThreatIntelligencePageProps) {
  const role = roleProp ?? getTieConsoleRole();
  const showOpsDetail = canViewTieOpsDetail(role);
  const canEditAi = canConfigureTieAi(role);
  const {
    enabled: tieEnabled,
    analyser,
    description: analyserDescription,
    error: tieModeError,
    refresh,
  } = useTieEngine();

  const [snapshot, setSnapshot] = useState<TieSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [intervalSec, setIntervalSec] = useState(refreshSeconds);
  const [lastSuccessLocal, setLastSuccessLocal] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const hasSnapshotRef = useRef(false);

  const [aiConfig, setAiConfig] = useState<TieAiConfig | null>(null);
  const [aiProvider, setAiProvider] = useState("mock");
  const [aiModel, setAiModel] = useState("");
  const [aiCustomModel, setAiCustomModel] = useState("");
  const [aiModels, setAiModels] = useState<TieAiConfig["models"]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiNotice, setAiNotice] = useState("");
  const [aiError, setAiError] = useState("");
  const [processStatus, setProcessStatus] = useState<TieProcessStatus | null>(null);
  const [processBusy, setProcessBusy] = useState(false);
  const [processError, setProcessError] = useState("");

  const refreshProcess = useCallback(async () => {
    try {
      const status = await fetchTieProcessStatus();
      setProcessStatus(status);
      setProcessError("");
      return status;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to read TIE process status";
      setProcessError(msg);
      return null;
    }
  }, []);

  const load = useCallback(async (manual = false) => {
    if (!tieEnabled) {
      setLoading(false);
      setRefreshing(false);
      setSnapshot(null);
      return;
    }
    if (manual) setRefreshing(true);
    else if (!hasSnapshotRef.current) setLoading(true);
    try {
      const next = await loadTieSnapshot(role);
      setSnapshot(next);
      hasSnapshotRef.current = true;
      if (next.lastSuccessAt) setLastSuccessLocal(next.lastSuccessAt);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [role, tieEnabled]);

  const loadAiConfig = useCallback(async () => {
    if (!tieEnabled) return;
    try {
      const cfg = await fetchTieAiConfig();
      setAiConfig(cfg);
      setAiProvider(cfg.provider);
      setAiModel(cfg.model);
      setAiModels(cfg.models || []);
      setAiError("");
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Could not load AI config");
    }
  }, [tieEnabled]);

  useEffect(() => {
    void load(false);
    void loadAiConfig();
  }, [role, load, loadAiConfig, tieEnabled]);

  useEffect(() => {
    void refreshProcess();
    const id = window.setInterval(() => {
      void refreshProcess();
    }, 5000);
    return () => window.clearInterval(id);
  }, [refreshProcess]);

  useEffect(() => {
    if (!tieEnabled || !autoRefresh) return;
    const id = window.setInterval(() => {
      void load(false);
    }, Math.max(10, intervalSec) * 1000);
    return () => window.clearInterval(id);
  }, [autoRefresh, intervalSec, load, tieEnabled]);

  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  async function onProviderChange(next: string) {
    setAiProvider(next);
    setAiCustomModel("");
    try {
      const models = await fetchTieAiModels(next);
      setAiModels(models);
      const preferred = models[0]?.id || "";
      setAiModel(preferred);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to load models");
    }
  }

  async function applyAiConfig() {
    if (!canEditAi) return;
    const model = (aiCustomModel.trim() || aiModel).trim();
    if (!model) {
      setAiError("Select or enter a model name");
      return;
    }
    setAiBusy(true);
    setAiError("");
    setAiNotice("");
    try {
      const cfg = await updateTieAiConfig({
        provider: aiProvider,
        model,
        persist: true,
      });
      setAiConfig(cfg);
      setAiProvider(cfg.provider);
      setAiModel(cfg.model);
      setAiModels(cfg.models || []);
      setAiCustomModel("");
      setAiNotice(`AI engine set to ${cfg.provider} · ${cfg.model}`);
      void load(true);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to update AI config");
    } finally {
      setAiBusy(false);
    }
  }
  const offline = snapshot?.offline ?? false;
  const status = snapshot?.status;
  const metrics = snapshot?.metrics;
  const pipeline = snapshot?.pipeline;
  const campaigns = snapshot?.campaigns;
  const healthComponents =
    snapshot?.health?.components || status?.system_health || null;

  const heartbeatLabel = useMemo(() => {
    void tick;
    return relativeTime(lastSuccessLocal || snapshot?.lastSuccessAt);
  }, [tick, lastSuccessLocal, snapshot?.lastSuccessAt]);

  async function onStartEngine() {
    setProcessBusy(true);
    setProcessError("");
    try {
      const result = await startTieProcess();
      setProcessStatus(result);
      await refresh();
      hasSnapshotRef.current = false;
      void load(true);
      void loadAiConfig();
      // Poll until healthy so the offline panel clears after uvicorn boots.
      for (let i = 0; i < 12; i += 1) {
        await new Promise((r) => window.setTimeout(r, 750));
        const status = await refreshProcess();
        if (status?.healthy) {
          void load(true);
          break;
        }
      }
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : "Failed to start TIE");
    } finally {
      setProcessBusy(false);
    }
  }

  async function onStopEngine() {
    setProcessBusy(true);
    setProcessError("");
    try {
      const result = await stopTieProcess();
      setProcessStatus(result);
      await refresh();
      setSnapshot(null);
      setLoading(false);
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : "Failed to stop TIE");
    } finally {
      setProcessBusy(false);
      void refreshProcess();
    }
  }

  const processRunning = Boolean(processStatus?.running || processStatus?.healthy);
  const processLabel = processBusy
    ? processRunning
      ? "Stopping…"
      : "Starting…"
    : processStatus?.healthy
      ? "Engine running · scrapes forward to TIE"
      : processRunning
        ? "Engine starting…"
        : "Engine stopped · Console built-in analyser";

  const engineControls = (
    <div className="tie-engine-switch-wrap">
      <div className="tie-process-controls">
        <button
          type="button"
          className="btn primary"
          disabled={processBusy || processRunning}
          onClick={() => void onStartEngine()}
        >
          {processBusy && !processRunning ? "Starting…" : "Start Engine"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={processBusy || !processRunning}
          onClick={() => void onStopEngine()}
        >
          {processBusy && processRunning ? "Stopping…" : "Stop Engine"}
        </button>
      </div>
      <p className="caption tie-process-status" title={analyserDescription}>
        <strong>{processRunning || tieEnabled ? "TIE" : "Console"}</strong>
        {" · "}
        {processLabel}
      </p>
      {processError || tieModeError ? (
        <p className="caption tie-ai-err" role="alert">
          {processError || tieModeError}
        </p>
      ) : null}
      {processStatus?.cwd ? (
        <p className="caption tie-process-path">TIE path: {processStatus.cwd}</p>
      ) : processStatus && processStatus.configured === false ? (
        <p className="caption tie-ai-err" role="status">
          Set <code>TIE_ENGINE_CWD</code> to your threat translation engine folder.
        </p>
      ) : null}
    </div>
  );

  if (!tieEnabled) {
    return (
      <div className="tie-page">
        <div className="page-header tie-page-header">
          <div>
            <h1>Threat Intelligence</h1>
            <p>
              TIE is off — Threat Console uses its built-in keyword and risk analyser on scrape
              data.
            </p>
          </div>
          {engineControls}
        </div>
        <section className="panel card tie-engine-disabled" role="status">
          <h2>Built-in Console analyser active</h2>
          <p className="caption">
            Dashboard, Threat Monitoring, and Analytics continue from scraped Mongo data
            (<code>keyword_filter</code> + <code>risk_scoring</code>). Click{" "}
            <strong>Start Engine</strong> to launch TIE, forward scrapes, and view ops metrics
            here.
          </p>
          <p className="caption">Current analyser: {analyser}</p>
        </section>
      </div>
    );
  }

  if (loading && !snapshot) {
    return (
      <div className="tie-page">
        <div className="page-header tie-page-header">
          <div>
            <h1>Threat Intelligence</h1>
            <p>Loading Threat Intelligence Engine status…</p>
          </div>
          {engineControls}
        </div>
      </div>
    );
  }

  if (offline && !status && !metrics) {
    return (
      <div className="tie-page">
        <div className="page-header tie-page-header">
          <div>
            <h1>Threat Intelligence</h1>
            <p>Operational window into the Threat Intelligence Engine.</p>
          </div>
          {engineControls}
        </div>
        <section className="panel card tie-offline" role="alert">
          <h2>Threat Intelligence Engine Offline</h2>
          <p className="caption">
            Last successful connection:{" "}
            {lastSuccessLocal ? new Date(lastSuccessLocal).toLocaleString() : "never"}
          </p>
          <p className="caption">
            The engine is not responding on {processStatus?.url || "http://127.0.0.1:8000"}.
            Use <strong>Start Engine</strong> to launch it from this dashboard (no Cursor
            terminal required).
          </p>
          <p className="caption">
            Or turn TIE off above to keep using the Console built-in scrape analyser.
          </p>
          <div className="tie-offline-actions">
            <button
              type="button"
              className="btn primary"
              disabled={processBusy}
              onClick={() => void onStartEngine()}
            >
              {processBusy ? "Starting…" : "Start Engine"}
            </button>
            <button type="button" className="btn" onClick={() => void load(true)}>
              Retry
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="tie-page">
      <div className="page-header tie-page-header">
        <div>
          <h1>Threat Intelligence</h1>
          <p>
            TIE health, processing, and pipeline — not a duplicate of Console analytics.
          </p>
        </div>
        <div className="tie-header-controls">
          {engineControls}
          <div className="tie-refresh-bar">
            <label className="check-row">
              <input
                type="checkbox"
                checked={autoRefresh}
                aria-label="Auto-refresh"
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              <span>Auto-refresh</span>
            </label>
            <label className="inline-number">
              every
              <input
                type="number"
                min={10}
                max={300}
                value={intervalSec}
                aria-label="TIE refresh interval seconds"
                onChange={(e) => setIntervalSec(Number(e.target.value) || DEFAULT_REFRESH_SEC)}
              />
              s
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={refreshing}
              onClick={() => void load(true)}
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>
      </div>

      {/* Section 1 — Engine status */}
      <section className="panel card tie-engine-hero">
        <div className="tie-engine-hero-main">
          <div>
            <div className="caption">Threat Intelligence Engine</div>
            <h2 className="tie-engine-title">
              <span className={statusDotClass(status?.status_display || status?.status)} aria-hidden="true" />
              {status?.status_display || status?.status || "Unknown"}
            </h2>
          </div>
          <div className="tie-engine-meta">
            <div>
              <em>Version</em>
              <strong>{status?.version || "—"}</strong>
            </div>
            <div>
              <em>Uptime</em>
              <strong>
                {status?.uptime_days != null ? `${status.uptime_days} days` : "—"}
              </strong>
            </div>
            <div>
              <em>Last heartbeat</em>
              <strong>{heartbeatLabel}</strong>
            </div>
            <div>
              <em>Connection</em>
              <strong>{status?.connection || "Threat Console ↔ TIE"}</strong>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2 — Processing overview */}
      <section className="tie-section">
        <div className="panel-head">
          <h2>Processing overview</h2>
          <span className="caption">Engine throughput — not Console analytics</span>
        </div>
        <div className="metric-grid">
          <StatCard
            label="Messages Processed"
            value={formatNumber(metrics?.messages_processed)}
            delta={`Today · ${formatNumber(metrics?.messages_today)}`}
            tone="primary"
          />
          <StatCard
            label="Intelligence Reports Generated"
            value={formatNumber(metrics?.intelligence_reports_generated)}
            tone="accent"
          />
          <StatCard
            label="Threats Detected"
            value={formatNumber(metrics?.threats_detected)}
            tone="danger"
          />
          <StatCard
            label="Active Campaigns"
            value={formatNumber(metrics?.active_campaigns)}
            tone="warning"
          />
          <StatCard
            label="Entities Extracted"
            value={formatNumber(metrics?.entities_extracted)}
            tone="success"
          />
          <StatCard
            label="Average Processing Time"
            value={
              metrics?.average_processing_time_sec != null
                ? `${metrics.average_processing_time_sec} sec/message`
                : "—"
            }
            tone="neutral"
          />
        </div>
      </section>

      {/* Section 3 — Pipeline */}
      <section className="panel card tie-section">
        <div className="panel-head">
          <h2>Pipeline status</h2>
          <span className="caption">End-to-end processing stages</span>
        </div>
        <div className="tie-pipeline" role="list">
          {(pipeline?.stages || []).map((stage, idx) => (
            <div key={stage.id} className="tie-pipeline-stage" role="listitem">
              {idx > 0 ? <div className="tie-pipeline-arrow" aria-hidden="true">↓</div> : null}
              <div className="tie-pipeline-card">
                <div className="tie-pipeline-name">{stage.name}</div>
                <div className={`tie-pipeline-status ${statusDotClass(stage.status)}`}>
                  <span className={statusDotClass(stage.status)} aria-hidden="true" />
                  {stage.status}
                </div>
                <div className="caption">Last: {relativeTime(stage.last_processed_at)}</div>
                <div className="caption">Workload: {stage.current_workload || "—"}</div>
              </div>
            </div>
          ))}
          {!pipeline?.stages?.length ? (
            <div className="empty-state">Pipeline status unavailable.</div>
          ) : null}
        </div>
      </section>

      {/* Section 4 — AI engine */}
      <section className="panel card tie-section">
        <div className="panel-head">
          <h2>AI engine status</h2>
          <span className="caption">Detection provider used by TIE pipelines</span>
        </div>
        <div className="metric-grid compact">
          <StatCard label="AI Provider" value={status?.ai?.provider || aiConfig?.provider || "—"} tone="primary" />
          <StatCard label="Model" value={status?.ai?.model || aiConfig?.model || "—"} tone="neutral" />
          <StatCard
            label="Requests today"
            value={formatNumber(status?.ai?.requests_today)}
            tone="accent"
          />
          <StatCard
            label="Average latency"
            value={
              status?.ai?.average_latency_ms != null
                ? `${status.ai.average_latency_ms} ms`
                : "—"
            }
            tone="neutral"
          />
          <StatCard
            label="Successful requests"
            value={formatNumber(status?.ai?.successful_requests)}
            tone="success"
          />
          <StatCard
            label="Failed requests"
            value={formatNumber(status?.ai?.failed_requests)}
            tone="danger"
          />
          {status?.ai?.token_usage != null ? (
            <StatCard label="Token usage" value={formatNumber(status.ai.token_usage)} tone="warning" />
          ) : null}
        </div>

        {canEditAi ? (
          <div className="tie-ai-picker" aria-label="TIE AI model selection">
            <div className="tie-ai-picker-row">
              <label className="field-block">
                <span className="field-label">Provider</span>
                <select
                  value={aiProvider}
                  aria-label="TIE AI provider"
                  disabled={aiBusy}
                  onChange={(e) => void onProviderChange(e.target.value)}
                >
                  {(aiConfig?.providers || [
                    { id: "mock", label: "Mock" },
                    { id: "openai", label: "OpenAI / OpenRouter" },
                    { id: "local", label: "Local LLM" },
                  ]).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-block">
                <span className="field-label">Model</span>
                <select
                  value={aiModels.some((m) => m.id === aiModel) ? aiModel : ""}
                  aria-label="TIE AI model"
                  disabled={aiBusy}
                  onChange={(e) => {
                    setAiModel(e.target.value);
                    setAiCustomModel("");
                  }}
                >
                  <option value="">Select model…</option>
                  {aiModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label || m.id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field-block">
                <span className="field-label">Custom model</span>
                <input
                  type="text"
                  value={aiCustomModel}
                  placeholder="optional override"
                  aria-label="TIE custom AI model"
                  disabled={aiBusy}
                  onChange={(e) => setAiCustomModel(e.target.value)}
                />
              </label>
              <div className="tie-ai-picker-actions">
                <button
                  type="button"
                  className="btn primary"
                  disabled={aiBusy}
                  onClick={() => void applyAiConfig()}
                >
                  {aiBusy ? "Applying…" : "Apply model"}
                </button>
              </div>
            </div>
            {aiNotice ? <p className="caption tie-ai-ok">{aiNotice}</p> : null}
            {aiError ? (
              <p className="caption tie-ai-err" role="alert">
                {aiError}
              </p>
            ) : null}
            {aiProvider === "openai" && aiConfig && !aiConfig.has_api_key ? (
              <p className="caption">
                No API key configured on TIE — set <code>AI_API_KEY</code> (or translation key) in TIE
                <code>.env</code>.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="caption tie-ai-readonly">
            Model selection requires Senior Analyst or Administrator.
          </p>
        )}
      </section>

      {/* Section 5 — Queue / workers (restricted) */}
      {showOpsDetail ? (
        <section className="panel card tie-section">
          <div className="panel-head">
            <h2>Queue and worker status</h2>
            <span className="caption">Senior Analyst / Administrator</span>
          </div>
          <div className="metric-grid compact">
            <StatCard
              label="Workers"
              value={
                snapshot?.workers
                  ? `${snapshot.workers.workers.running} / ${snapshot.workers.workers.total}`
                  : "—"
              }
              delta={snapshot?.workers?.status}
              tone="primary"
            />
            <StatCard
              label="Pending jobs"
              value={formatNumber(snapshot?.queue?.pending_jobs)}
              tone="warning"
            />
            <StatCard
              label="Processing jobs"
              value={formatNumber(snapshot?.queue?.processing_jobs)}
              tone="accent"
            />
            <StatCard
              label="Failed jobs"
              value={formatNumber(snapshot?.queue?.failed_jobs)}
              tone="danger"
            />
            <StatCard
              label="Retry queue"
              value={formatNumber(snapshot?.queue?.retry_queue)}
              tone="warning"
            />
            <StatCard
              label="Dead letter queue"
              value={formatNumber(snapshot?.queue?.dead_letter_queue)}
              tone="danger"
            />
          </div>
        </section>
      ) : (
        <section className="panel card tie-section tie-restricted">
          <div className="panel-head">
            <h2>Queue and worker status</h2>
            <span className="caption">Restricted — Senior Analyst / Administrator only</span>
          </div>
        </section>
      )}

      {/* Section 6 — Recent intelligence */}
      <section className="panel card tie-section">
        <div className="panel-head">
          <h2>Intelligence output</h2>
          <span className="caption">Recent reports · latest 10</span>
        </div>
        {!snapshot?.recent?.length ? (
          <div className="empty-state">No recent intelligence reports.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Category</th>
                  <th>Risk</th>
                  <th>Confidence</th>
                  <th>Generated</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.recent.map((item) => (
                  <tr key={item.id}>
                    <td>{item.title}</td>
                    <td>{formatLabel(item.category)}</td>
                    <td>
                      <span className={`risk-badge risk-${String(item.risk || "low").toLowerCase()}`}>
                        {formatLabel(item.risk)}
                      </span>
                    </td>
                    <td className="mono">{formatLabel(item.confidence)}%</td>
                    <td className="mono">{relativeTime(item.generated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 7 — Campaigns */}
      <section className="panel card tie-section">
        <div className="panel-head">
          <h2>Campaign activity</h2>
        </div>
        <div className="metric-grid compact">
          <StatCard
            label="Active campaigns"
            value={formatNumber(campaigns?.active_campaigns)}
            tone="primary"
          />
          <StatCard
            label="New campaigns today"
            value={formatNumber(campaigns?.new_campaigns_today)}
            tone="accent"
          />
          <StatCard
            label="Updated campaigns"
            value={formatNumber(campaigns?.updated_campaigns)}
            tone="warning"
          />
        </div>
        {campaigns?.highest_risk_campaign ? (
          <div className="tie-highest-campaign">
            <div className="caption">Highest risk campaign</div>
            <div className="tie-highest-campaign-row">
              <strong>{campaigns.highest_risk_campaign.campaign_id}</strong>
              <span>{formatLabel(campaigns.highest_risk_campaign.category)}</span>
              <span className="risk-badge risk-high">
                Risk {campaigns.highest_risk_campaign.risk_score}
              </span>
            </div>
          </div>
        ) : (
          <div className="empty-state">No campaign data.</div>
        )}
      </section>

      {/* Section 8 — System health */}
      <section className="panel card tie-section">
        <div className="panel-head">
          <h2>System health</h2>
        </div>
        <div className="tie-health-grid">
          {(
            [
              ["Database", healthComponents?.database?.status],
              ["Redis", healthComponents?.redis?.status],
              ["Workers", healthComponents?.workers?.status],
              ["LLM Provider", healthComponents?.llm_provider?.status],
              ["Threat Console Sync", healthComponents?.threat_console_sync?.status],
            ] as Array<[string, string | undefined]>
          ).map(([label, value]) => (
            <div key={label} className="tie-health-item">
              <span className={statusDotClass(value)} aria-hidden="true" />
              <div>
                <strong>{label}</strong>
                <div className="caption">{value || "—"}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
