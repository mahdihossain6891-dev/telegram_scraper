"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  clearAiCache,
  reloadPromptTemplates,
  testAiProvider,
} from "@/components/ai/api";
import {
  estimateModelCharacteristics,
  starsLabel,
} from "@/components/ai/controlCenter/estimates";
import {
  AI_PROFILES,
  CONTROL_SECTIONS,
  GENERATION_DEFAULTS,
  SETTING_TOOLTIPS,
  type AiProfileId,
  type ControlSectionId,
} from "@/components/ai/controlCenter/profiles";
import { useModelDiscovery } from "@/components/ai/controlCenter/useModelDiscovery";
import {
  createEmptyCase,
  getInvestigationState,
  selectActiveCases,
  setInvestigationState,
  updateInvestigationState,
  useInvestigationStore,
} from "@/components/ai/store";
import { formatLatency } from "@/components/ai/utils";

function healthEmoji(status?: string | null): string {
  if (status === "healthy") return "🟢";
  if (status === "slow") return "🟡";
  return "🔴";
}

function healthLabel(status?: string | null): string {
  if (status === "healthy") return "Healthy";
  if (status === "slow") return "Slow";
  if (status === "offline") return "Offline";
  return status || "Unknown";
}

function yesNo(v?: boolean): string {
  return v ? "Yes" : "No";
}

function FieldTip({ text }: { text: string }) {
  return (
    <span className="ai-cc-tip" title={text} aria-label={text}>
      ?
    </span>
  );
}

type Props = {
  onRefreshConnection: () => void;
};

export function ControlCenterDrawer({ onRefreshConnection }: Props) {
  const open = useInvestigationStore((s) => s.controlCenterOpen);
  const section = useInvestigationStore((s) => s.controlCenterSection);
  const scrollTop = useInvestigationStore((s) => s.controlCenterScrollTop);
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const { loadProviders, loadModels, changeProvider, changeModel } = useModelDiscovery();
  const [actionMsg, setActionMsg] = useState("");
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    void loadProviders(false);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setInvestigationState({ controlCenterOpen: false });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, loadProviders]);

  useEffect(() => {
    if (!open || !bodyRef.current) return;
    bodyRef.current.scrollTop = scrollTop;
  }, [open, scrollTop]);

  if (!open) return null;

  const setSection = (id: ControlSectionId) =>
    setInvestigationState({ controlCenterSection: id });

  const onBodyScroll = () => {
    const el = bodyRef.current;
    if (!el) return;
    setInvestigationState({ controlCenterScrollTop: el.scrollTop });
  };

  return (
    <div
      className="ai-cc-backdrop"
      role="presentation"
      onClick={() => setInvestigationState({ controlCenterOpen: false })}
    >
      <aside
        ref={panelRef}
        className="ai-cc-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="ai-cc-header">
          <div>
            <h2 id={titleId}>AI Control Center</h2>
            <p className="caption">Configure Sebastian without interrupting the investigation.</p>
          </div>
          <button
            type="button"
            className="btn ai-btn-ghost"
            onClick={() => setInvestigationState({ controlCenterOpen: false })}
          >
            Close
          </button>
        </header>

        <nav className="ai-cc-nav" aria-label="Control Center sections">
          {CONTROL_SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`ai-cc-nav-btn${section === s.id ? " active" : ""}`}
              onClick={() => setSection(s.id)}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div ref={bodyRef} className="ai-cc-body" onScroll={onBodyScroll}>
          {section === "general" ? <GeneralSection /> : null}
          {section === "model" ? (
            <ModelSection
              changeProvider={changeProvider}
              changeModel={changeModel}
              onRefresh={() => {
                const p = getInvestigationState().selectedProvider;
                if (p) void loadModels(p, true);
                else void loadProviders(true);
              }}
            />
          ) : null}
          {section === "generation" ? <GenerationSection /> : null}
          {section === "performance" ? <PerformanceSection /> : null}
          {section === "advanced" ? (
            <AdvancedSection
              actionMsg={actionMsg}
              actionBusy={actionBusy}
              setActionMsg={setActionMsg}
              setActionBusy={setActionBusy}
              loadProviders={loadProviders}
              loadModels={loadModels}
              onRefreshConnection={onRefreshConnection}
            />
          ) : null}
          {section === "about" ? <AboutSection /> : null}
        </div>
      </aside>
    </div>
  );
}

function GeneralSection() {
  const {
    selectedProvider,
    selectedModel,
    preferStreaming,
    availableModels,
    providerHealthDetail,
    activeId,
    sessions,
  } = useInvestigationStore();
  const meta = availableModels.find((m) => m.model_id === selectedModel);
  const health = providerHealthDetail;
  const active = sessions.find((s) => s.id === activeId);

  return (
    <section className="ai-cc-section" aria-label="General">
      <h3>General</h3>
      <dl className="ai-cc-kv">
        <div>
          <dt>Current provider</dt>
          <dd>{selectedProvider || "—"}</dd>
        </div>
        <div>
          <dt>Current model</dt>
          <dd>{selectedModel || meta?.display_name || "—"}</dd>
        </div>
        <div>
          <dt>Connection status</dt>
          <dd>
            {healthEmoji(health?.status)} {healthLabel(health?.status)}
          </dd>
        </div>
        <div>
          <dt>Model health</dt>
          <dd>{health?.detail || health?.ok ? "Reachable" : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Context window</dt>
          <dd>{meta?.context_window ? meta.context_window.toLocaleString() : "—"}</dd>
        </div>
        <div>
          <dt>Streaming status</dt>
          <dd>{preferStreaming ? "Preferred on" : "Preferred off"}</dd>
        </div>
        <div>
          <dt>Current session</dt>
          <dd>{active?.title || activeId || "—"}</dd>
        </div>
      </dl>
    </section>
  );
}

function ModelSection({
  changeProvider,
  changeModel,
  onRefresh,
}: {
  changeProvider: (id: string) => Promise<void>;
  changeModel: (id: string) => void;
  onRefresh: () => void;
}) {
  const {
    selectedProvider,
    selectedModel,
    availableProviders,
    availableModels,
    modelsLoading,
    modelsError,
    providerHealthDetail,
    modelsLastRefreshAt,
  } = useInvestigationStore();

  const meta = availableModels.find((m) => m.model_id === selectedModel) || null;
  const estimates = useMemo(() => estimateModelCharacteristics(meta), [meta]);
  const health = providerHealthDetail;

  return (
    <section className="ai-cc-section" aria-label="Model">
      <h3>Model</h3>
      <p className="caption">
        Switching provider or model applies to future requests only. Conversations, evidence,
        and saved cases are never cleared.
      </p>

      <div className="ai-cc-row">
        <label className="ai-cc-field">
          <span>
            Provider <FieldTip text={SETTING_TOOLTIPS.provider} />
          </span>
          <select
            value={selectedProvider}
            disabled={modelsLoading}
            onChange={(e) => void changeProvider(e.target.value)}
          >
            {!selectedProvider ? <option value="">Select provider…</option> : null}
            {availableProviders.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={modelsLoading}
          onClick={onRefresh}
          title="Re-query models and refresh cache"
        >
          Refresh
        </button>
      </div>

      <div className="ai-cc-health-line" title={health?.detail || ""}>
        {healthEmoji(health?.status)} {healthLabel(health?.status)}
        {health?.latency_ms != null ? ` · ${health.latency_ms} ms` : ""}
        {health?.models_available != null ? ` · ${health.models_available} models` : ""}
        {modelsLastRefreshAt
          ? ` · refreshed ${new Date(modelsLastRefreshAt).toLocaleTimeString()}`
          : ""}
      </div>

      <label className="ai-cc-field">
        <span>
          Model <FieldTip text={SETTING_TOOLTIPS.model} />
        </span>
        <select
          value={selectedModel}
          disabled={modelsLoading || !selectedProvider}
          onChange={(e) => changeModel(e.target.value)}
        >
          {!selectedModel ? (
            <option value="">{modelsLoading ? "Loading…" : "Select model…"}</option>
          ) : null}
          {availableModels.map((m) => (
            <option key={m.model_id} value={m.model_id}>
              {m.display_name || m.model_id}
            </option>
          ))}
        </select>
      </label>

      {modelsLoading ? <p className="caption">Loading models…</p> : null}
      {modelsError ? <p className="ai-cc-error">{modelsError}</p> : null}

      {estimates && meta ? (
        <div className="ai-cc-estimates" aria-label="Estimated characteristics">
          <h4>{meta.display_name || meta.model_id}</h4>
          <ul>
            <li>
              <span>Reasoning</span> {starsLabel(estimates.reasoning)}
            </li>
            <li>
              <span>Speed</span> {starsLabel(estimates.speed)}
            </li>
            <li>
              <span>Cost</span> {starsLabel(estimates.cost)}
            </li>
            <li>
              <span>Investigation quality</span> {starsLabel(estimates.investigation)}
            </li>
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function GenerationSection() {
  const {
    temperature,
    topP,
    maxTokens,
    preferStreaming,
    stopSequences,
    aiProfile,
  } = useInvestigationStore();

  const applyProfile = (id: AiProfileId) => {
    const profile = AI_PROFILES.find((p) => p.id === id);
    if (!profile) return;
    if (id === "custom") {
      setInvestigationState({ aiProfile: "custom" });
      return;
    }
    setInvestigationState({
      aiProfile: id,
      temperature: profile.values.temperature,
      topP: profile.values.topP,
      maxTokens: profile.values.maxTokens,
      preferStreaming: profile.values.preferStreaming,
      stopSequences: profile.values.stopSequences,
    });
  };

  const markCustom = () => {
    if (aiProfile !== "custom") setInvestigationState({ aiProfile: "custom" });
  };

  return (
    <section className="ai-cc-section" aria-label="Generation">
      <h3>Generation</h3>

      <fieldset className="ai-cc-profiles">
        <legend>
          AI profile <FieldTip text={SETTING_TOOLTIPS.profile} />
        </legend>
        <div className="ai-cc-profile-grid">
          {AI_PROFILES.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`ai-cc-profile-btn${aiProfile === p.id ? " active" : ""}`}
              title={p.description}
              onClick={() => applyProfile(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="ai-cc-field">
        <span>
          Temperature ({temperature.toFixed(2)}) <FieldTip text={SETTING_TOOLTIPS.temperature} />
        </span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={temperature}
          onChange={(e) => {
            markCustom();
            setInvestigationState({ temperature: Number(e.target.value) });
          }}
        />
      </label>

      <label className="ai-cc-field">
        <span>
          Top P ({topP.toFixed(2)}) <FieldTip text={SETTING_TOOLTIPS.topP} />
        </span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={topP}
          onChange={(e) => {
            markCustom();
            setInvestigationState({ topP: Number(e.target.value) });
          }}
        />
      </label>

      <label className="ai-cc-field">
        <span>
          Maximum tokens <FieldTip text={SETTING_TOOLTIPS.maxTokens} />
        </span>
        <input
          type="number"
          min={64}
          max={128000}
          step={64}
          value={maxTokens}
          onChange={(e) => {
            markCustom();
            setInvestigationState({
              maxTokens: Math.max(64, Number(e.target.value) || 64),
            });
          }}
        />
      </label>

      <label className="ai-cc-field ai-cc-check">
        <input
          type="checkbox"
          checked={preferStreaming}
          onChange={(e) => {
            markCustom();
            setInvestigationState({ preferStreaming: e.target.checked });
          }}
        />
        <span>
          Streaming <FieldTip text={SETTING_TOOLTIPS.streaming} />
        </span>
      </label>

      <label className="ai-cc-field">
        <span>
          Stop sequences <FieldTip text={SETTING_TOOLTIPS.stopSequences} />
        </span>
        <input
          type="text"
          placeholder="optional, comma-separated"
          value={stopSequences}
          onChange={(e) => {
            markCustom();
            setInvestigationState({ stopSequences: e.target.value });
          }}
        />
      </label>

      <button
        type="button"
        className="btn ai-btn-ghost"
        onClick={() =>
          setInvestigationState({
            aiProfile: "balanced",
            ...GENERATION_DEFAULTS,
          })
        }
      >
        Reset to defaults
      </button>
    </section>
  );
}

function PerformanceSection() {
  const { perfMetrics, latencyMs, providerHealthDetail } = useInvestigationStore();
  const avg =
    perfMetrics.responseCount > 0
      ? Math.round(perfMetrics.totalLatencyMs / perfMetrics.responseCount)
      : null;
  const avgTokens =
    perfMetrics.responseCount > 0
      ? Math.round(perfMetrics.totalTokensEstimate / perfMetrics.responseCount)
      : null;
  const cacheTotal = perfMetrics.cacheHits + perfMetrics.cacheMisses;
  const hitRate =
    cacheTotal > 0 ? `${Math.round((perfMetrics.cacheHits / cacheTotal) * 100)}%` : "—";

  return (
    <section className="ai-cc-section" aria-label="Performance">
      <h3>Performance</h3>
      <dl className="ai-cc-kv">
        <div>
          <dt>Average response time</dt>
          <dd>{avg != null ? formatLatency(avg) : "—"}</dd>
        </div>
        <div>
          <dt>Average tokens</dt>
          <dd>{avgTokens != null ? avgTokens.toLocaleString() : "—"}</dd>
        </div>
        <div>
          <dt>Cache hit rate</dt>
          <dd>{hitRate}</dd>
        </div>
        <div>
          <dt>Prompt version</dt>
          <dd>{perfMetrics.promptVersion || "—"}</dd>
        </div>
        <div>
          <dt>Last response time</dt>
          <dd>{formatLatency(perfMetrics.lastLatencyMs ?? latencyMs)}</dd>
        </div>
        <div>
          <dt>Provider latency</dt>
          <dd>
            {providerHealthDetail?.latency_ms != null
              ? `${providerHealthDetail.latency_ms} ms`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Session token usage</dt>
          <dd>{perfMetrics.sessionTokensEstimate.toLocaleString()}</dd>
        </div>
      </dl>
    </section>
  );
}

function AdvancedSection({
  actionMsg,
  actionBusy,
  setActionMsg,
  setActionBusy,
  loadProviders,
  loadModels,
  onRefreshConnection,
}: {
  actionMsg: string;
  actionBusy: boolean;
  setActionMsg: (s: string) => void;
  setActionBusy: (b: boolean) => void;
  loadProviders: (refresh?: boolean) => Promise<void>;
  loadModels: (provider: string, refresh?: boolean) => Promise<unknown>;
  onRefreshConnection: () => void;
}) {
  const run = async (label: string, fn: () => Promise<void>) => {
    setActionBusy(true);
    setActionMsg("");
    try {
      await fn();
      setActionMsg(label);
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionBusy(false);
    }
  };

  const exportMetadata = () => {
    const st = getInvestigationState();
    const active = st.sessions.find((s) => s.id === st.activeId);
    const payload = {
      exported_at: new Date().toISOString(),
      provider: st.selectedProvider,
      model: st.selectedModel,
      temperature: st.temperature,
      top_p: st.topP,
      max_tokens: st.maxTokens,
      streaming: st.preferStreaming,
      profile: st.aiProfile,
      session_id: active?.serverSessionId || active?.id || null,
      session_title: active?.title || null,
      message_count: active?.messages.length ?? 0,
      latency_ms: st.latencyMs,
      perf: st.perfMetrics,
      note: "Metadata only — no message bodies or evidence payloads.",
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sebastien-session-meta-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setActionMsg("Session metadata exported.");
  };

  const resetClientSession = () => {
    updateInvestigationState((prev) => {
      const blank = createEmptyCase();
      const sessions = prev.sessions.map((s) =>
        s.id === prev.activeId
          ? {
              ...s,
              messages: [],
              updatedAt: new Date().toISOString(),
              description: "Session reset (client only)",
              serverSessionId: null,
            }
          : s,
      );
      const active = selectActiveCases(sessions).find((s) => s.id === prev.activeId);
      if (!active) sessions.push(blank);
      return {
        ...prev,
        sessions,
        activeId: active?.id || blank.id,
        evidence: { citations: [], retrieved: [] },
        draft: "",
        report: null,
        showReportForm: false,
        perfMetrics: {
          ...prev.perfMetrics,
          sessionTokensEstimate: 0,
          lastLatencyMs: null,
        },
        error: "",
      };
    });
    setActionMsg("Client session reset. Production intel data was not modified.");
  };

  return (
    <section className="ai-cc-section" aria-label="Advanced">
      <h3>Advanced</h3>
      <p className="caption">
        These actions affect Sebastian configuration and caches only — never production intel
        collections.
      </p>
      <div className="ai-cc-actions">
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={() =>
            void run("AI model cache cleared.", async () => {
              await clearAiCache();
              const p = getInvestigationState().selectedProvider;
              if (p) await loadModels(p, true);
            })
          }
        >
          Clear AI cache
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={() =>
            void run("Models refreshed.", async () => {
              const p = getInvestigationState().selectedProvider;
              if (p) await loadModels(p, true);
              else await loadProviders(true);
            })
          }
        >
          Refresh models
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={() =>
            void run("Provider reconnected.", async () => {
              await loadProviders(true);
              onRefreshConnection();
            })
          }
        >
          Reconnect provider
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={() =>
            void run("Provider test completed.", async () => {
              const p = getInvestigationState().selectedProvider;
              const result = await testAiProvider(p || undefined);
              if (!result.ok) throw new Error(result.detail || "Provider test failed");
              setInvestigationState({
                providerHealthDetail: {
                  ok: result.ok,
                  status: result.status,
                  latency_ms: result.latency_ms,
                  models_available: result.models_available,
                  detail: result.detail,
                },
              });
            })
          }
        >
          Test provider
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={() =>
            void run("Prompt templates reloaded.", async () => {
              const res = await reloadPromptTemplates();
              if (res.prompt_version) {
                setInvestigationState({
                  perfMetrics: {
                    ...getInvestigationState().perfMetrics,
                    promptVersion: res.prompt_version,
                  },
                });
              }
            })
          }
        >
          Reload prompt templates
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={resetClientSession}
        >
          Reset session
        </button>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={actionBusy}
          onClick={exportMetadata}
        >
          Export session metadata
        </button>
      </div>
      {actionMsg ? <p className="ai-cc-action-msg">{actionMsg}</p> : null}
    </section>
  );
}

function AboutSection() {
  const {
    selectedProvider,
    selectedModel,
    availableModels,
    preferStreaming,
    providerHealthDetail,
  } = useInvestigationStore();
  const meta = availableModels.find((m) => m.model_id === selectedModel);
  const caps = meta?.capabilities || {};
  const ownedBy = typeof meta?.raw?.owned_by === "string" ? meta.raw.owned_by : "—";
  const contextLabel = meta?.context_window
    ? meta.context_window.toLocaleString()
    : "—";

  return (
    <section className="ai-cc-section" aria-label="About">
      <h3>About</h3>
      <dl className="ai-cc-kv">
        <div>
          <dt>Provider</dt>
          <dd>{selectedProvider || "—"}</dd>
        </div>
        <div>
          <dt>Selected model</dt>
          <dd>{meta?.display_name || selectedModel || "—"}</dd>
        </div>
        <div>
          <dt>Provider version</dt>
          <dd>{ownedBy}</dd>
        </div>
        <div>
          <dt>Context window</dt>
          <dd>{contextLabel}</dd>
        </div>
        <div>
          <dt>Streaming</dt>
          <dd>{yesNo(caps.supports_streaming ?? preferStreaming)}</dd>
        </div>
        <div>
          <dt>JSON mode</dt>
          <dd>{yesNo(caps.supports_json_output)}</dd>
        </div>
        <div>
          <dt>Reasoning support</dt>
          <dd>{yesNo(caps.supports_reasoning)}</dd>
        </div>
        <div>
          <dt>Vision support</dt>
          <dd>{yesNo(caps.supports_vision)}</dd>
        </div>
        <div>
          <dt>Tool calling</dt>
          <dd>{yesNo(caps.supports_tool_calling)}</dd>
        </div>
        <div>
          <dt>Health</dt>
          <dd>
            {healthEmoji(providerHealthDetail?.status)}{" "}
            {healthLabel(providerHealthDetail?.status)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
