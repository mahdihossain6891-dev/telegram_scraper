"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef } from "react";
import Link from "next/link";

import { fetchAiHealth, generateReport, postAi } from "@/components/ai/api";
import { ControlCenterDrawer } from "@/components/ai/controlCenter/ControlCenterDrawer";
import { EmptyState } from "@/components/ai/EmptyState";
import { ActionBriefPanel } from "@/components/ai/ActionBriefPanel";
import { EvidencePanel } from "@/components/ai/EvidencePanel";
import { InvestigationHeader } from "@/components/ai/InvestigationHeader";
import { InvestigationResultCard } from "@/components/ai/InvestigationResultCard";
import {
  InvestigationSearch,
  type InvestigationSearchHandle,
} from "@/components/ai/InvestigationSearch";
import { InvestigationWorkspaceBar } from "@/components/ai/InvestigationWorkspaceBar";
import { ConsoleJumpNav } from "@/components/layout/ConsoleJumpNav";
import { SimulationBanner } from "@/components/mode/SimulationBanner";
import { useDataMode } from "@/components/mode/DataModeProvider";
import type { InvestigationWorkflow } from "@/components/ai/InvestigationWorkflowPanel";
import { ModelSettingsPanel } from "@/components/ai/ModelSettingsPanel";
import { QuickActions } from "@/components/ai/QuickActions";
import { SavedCasesPanel } from "@/components/ai/SavedCasesPanel";
import { SuggestedActions } from "@/components/ai/SuggestedActions";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import {
  createEmptyCase,
  getInvestigationState,
  healthIsFresh,
  openControlCenter,
  recordAiResponseMetrics,
  selectActiveCases,
  setInvestigationState,
  updateInvestigationState,
  useInvestigationStore,
  useIsClient,
} from "@/components/ai/store";
import type { AiCitation, AiRetrieved, ChatMessage, Confidence } from "@/components/ai/types";
import {
  DEFAULT_SEARCH_PLACEHOLDER,
  QUICK_ACTIONS,
  REPORT_TYPES,
  getQuickAction,
} from "@/components/ai/types";
import { parseThreatReport } from "@/components/ai/threat-report";
import {
  buildInvestigationQuery,
  composeActionQuery,
  confidenceClass,
  dedupeEntityCandidates,
  extractNumericSubject,
  isTargetlessInvestigationQuery,
  lastAssistant,
  riskFromConfidence,
  uid,
} from "@/components/ai/utils";

export function AiCopilotApp() {
  const isClient = useIsClient();
  const { mode, simulation } = useDataMode();
  const isSim = mode === "simulation" && simulation.simulation_active;
  const state = useInvestigationStore();
  const {
    view,
    sessions,
    activeId,
    draft,
    activeActionId,
    searchPlaceholder,
    targetGate,
    entityKind,
    entityValue,
    evidence,
    evidenceCollapsed,
    evidenceCardOpen,
    report,
    reportType,
    reportSubjectId,
    reportSubjectType,
    reportNotes,
    showReportForm,
    latencyMs,
    lastModel,
    selectedModel,
    selectedProvider,
    providerHealthDetail,
    availableProviders,
    health,
    workspaceScrollTop,
    error,
    busy,
    temperature,
    maxTokens,
  } = state;

  const workspaceRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<InvestigationSearchHandle>(null);
  const skipScrollSave = useRef(false);
  const didRestoreScroll = useRef(false);
  const scrollSaveTimer = useRef<number | null>(null);

  const active = useMemo(() => {
    const activeSessions = selectActiveCases(sessions);
    return activeSessions.find((s) => s.id === activeId) || activeSessions[0] || null;
  }, [sessions, activeId]);

  // Drop dismissed sessions from the "current" pointer without wiping archived records.
  useEffect(() => {
    if (!activeId) return;
    const current = sessions.find((s) => s.id === activeId);
    if (current && (current.status || "active") === "dismissed") {
      const next = selectActiveCases(sessions)[0];
      if (next) setInvestigationState({ activeId: next.id });
    }
  }, [activeId, sessions]);

  const refreshHealth = useCallback(async (force = false) => {
    if (!force && healthIsFresh(getInvestigationState())) return;
    try {
      const h = await fetchAiHealth();
      setInvestigationState({
        health: h,
        healthFetchedAt: Date.now(),
        error: "",
      });
    } catch (e) {
      setInvestigationState({
        health: null,
        healthFetchedAt: Date.now(),
        error: e instanceof Error ? e.message : "AI health unavailable",
      });
    }
  }, []);

  useEffect(() => {
    void refreshHealth(true);
  }, [refreshHealth, mode, simulation.simulation_active, simulation.session_id]);

  // Restore workspace scroll after mount / navigation return.
  useEffect(() => {
    if (didRestoreScroll.current) return;
    const el = workspaceRef.current;
    if (!el) return;
    didRestoreScroll.current = true;
    skipScrollSave.current = true;
    el.scrollTop = workspaceScrollTop;
    const t = window.setTimeout(() => {
      skipScrollSave.current = false;
    }, 50);
    return () => window.clearTimeout(t);
  }, [workspaceScrollTop]);

  // Keep scroll near bottom when new messages arrive (not when restoring).
  useEffect(() => {
    const el = workspaceRef.current;
    if (!el || busy) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (nearBottom) {
      skipScrollSave.current = true;
      el.scrollTop = el.scrollHeight;
      setInvestigationState({ workspaceScrollTop: el.scrollTop });
      window.setTimeout(() => {
        skipScrollSave.current = false;
      }, 50);
    }
  }, [active?.messages.length, busy]);

  const onWorkspaceScroll = () => {
    const el = workspaceRef.current;
    if (!el || skipScrollSave.current) return;
    if (scrollSaveTimer.current) window.clearTimeout(scrollSaveTimer.current);
    scrollSaveTimer.current = window.setTimeout(() => {
      setInvestigationState({ workspaceScrollTop: el.scrollTop });
    }, 150);
  };

  useEffect(() => {
    return () => {
      if (scrollSaveTimer.current) window.clearTimeout(scrollSaveTimer.current);
      const el = workspaceRef.current;
      if (el) setInvestigationState({ workspaceScrollTop: el.scrollTop });
    };
  }, []);

  const applyEvidence = (
    citations: AiCitation[] | undefined,
    retrieved: AiRetrieved[] | undefined,
    confidence?: Confidence,
  ) => {
    setInvestigationState({
      evidence: {
        citations: citations || [],
        retrieved: retrieved || [],
        confidence,
      },
    });
  };

  const startNewInvestigation = () => {
    const session = createEmptyCase();
    updateInvestigationState((prev) => ({
      ...prev,
      sessions: [session, ...prev.sessions],
      activeId: session.id,
      evidence: { citations: [], retrieved: [] },
      evidenceCardOpen: {},
      report: null,
      showReportForm: false,
      draft: "",
      activeActionId: null,
      searchPlaceholder: DEFAULT_SEARCH_PLACEHOLDER,
      targetGate: null,
      entityKind: null,
      entityValue: "",
      view: "investigation",
      workspaceScrollTop: 0,
    }));
  };

  const focusSearch = () => {
    window.requestAnimationFrame(() => searchRef.current?.focus());
  };

  const showTargetRequired = (actionId?: string | null) => {
    const action = QUICK_ACTIONS.find((a) => a.id === actionId);
    const title = "No investigation target selected";
    let message =
      "Please search for and select a monitored user before starting an investigation.";
    if (actionId === "analyze_behavior") {
      message =
        "Please select a valid monitored user before analyzing behavioral activity.";
    } else if (actionId === "explain_alert") {
      message = "Please search for a valid alert ID or user before explaining an alert.";
    } else if (actionId === "generate_report") {
      message =
        "Please select a completed investigation (subject ID) before generating a report.";
    } else if (actionId === "related_users") {
      message =
        "Please search for and select a monitored user before finding related users.";
    } else if (action) {
      message = `Please search for and select a monitored entity before starting “${action.label}”.`;
    }
    setInvestigationState({
      targetGate: { title, message, actionId: actionId || null },
      view: "investigation",
      showReportForm: actionId === "generate_report" ? true : false,
    });
    focusSearch();
  };

  const prepareAction = (actionId: string) => {
    const action = getQuickAction(actionId);
    if (!action) return;

    if (actionId === "generate_report") {
      setInvestigationState({
        activeActionId: actionId,
        searchPlaceholder: action.placeholder,
        showReportForm: true,
        targetGate: {
          title: action.label,
          message: `${action.description}\n\n${action.targetHint}.`,
          actionId,
        },
        view: "investigation",
      });
      focusSearch();
      return;
    }

    setInvestigationState({
      activeActionId: actionId,
      searchPlaceholder: action.placeholder,
      showReportForm: false,
      targetGate: {
        title: action.label,
        message: `${action.description}\n\n${action.targetHint}.`,
        actionId,
      },
      view: "investigation",
    });
    focusSearch();
  };

  const selectCase = (id: string) => {
    const session = selectActiveCases(sessions).find((s) => s.id === id);
    if (!session) return;
    const last = lastAssistant(session);
    setInvestigationState({
      activeId: id,
      view: "investigation",
      report: null,
      showReportForm: false,
      error: "",
      targetGate: null,
      evidence: last
        ? {
            citations: last.citations || [],
            retrieved: last.retrieved || [],
            confidence: last.confidence,
          }
        : { citations: [], retrieved: [] },
      workspaceScrollTop: 0,
    });
  };

  const appendExchange = (
    sessionId: string,
    userMsg: ChatMessage,
    assistantMsg: ChatMessage,
    serverSessionId?: string | null,
  ) => {
    updateInvestigationState((prev) => ({
      ...prev,
      sessions: prev.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const title =
          s.messages.length === 0
            ? userMsg.content.slice(0, 52) || s.title
            : s.title;
        return {
          ...s,
          title,
          description: userMsg.content.slice(0, 120),
          risk: riskFromConfidence(assistantMsg.confidence, assistantMsg.refused),
          serverSessionId: serverSessionId || s.serverSessionId,
          messages: [...s.messages, userMsg, assistantMsg],
          updatedAt: new Date().toISOString(),
        };
      }),
    }));
  };

  const runInvestigation = async (
    rawText: string,
    options?: {
      subjectOverride?: { user_id?: number; chat_id?: number };
      /** When selecting from ambiguous results, keep the analyst's original question. */
      preserveDraft?: boolean;
      /** Skip client target gate (entity already chosen / follow-up with bound subject). */
      allowWithoutTarget?: boolean;
    },
  ) => {
    if (!active || busy) return;

    const action = QUICK_ACTIONS.find((a) => a.id === activeActionId);
    const composed = composeActionQuery(
      activeActionId,
      rawText,
      action?.queryTemplate,
    );
    const text = buildInvestigationQuery(
      composed || rawText,
      entityKind,
      entityValue,
    );
    if (!text.trim()) {
      showTargetRequired(activeActionId);
      return;
    }

    const subject =
      options?.subjectOverride ||
      extractNumericSubject(entityKind, entityValue) ||
      undefined;

    // Never start an investigation without a concrete target.
    if (
      !options?.allowWithoutTarget &&
      !subject &&
      !entityValue.trim() &&
      isTargetlessInvestigationQuery(text)
    ) {
      showTargetRequired(activeActionId);
      return;
    }

    setInvestigationState({
      busy: true,
      error: "",
      targetGate: null,
      draft: options?.preserveDraft ? getInvestigationState().draft : "",
      showReportForm: false,
      view: "investigation",
    });

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };

    const started = performance.now();
    const sessionId = active.id;
    const serverSessionId = active.serverSessionId;

    try {
      const data = await postAi<{
        answer: string;
        session_id?: string;
        citations?: AiCitation[];
        retrieved?: AiRetrieved[];
        confidence?: Confidence;
        intent?: string;
        refused?: boolean;
        model?: string;
        metadata?: {
          status?: string;
          workflow?: InvestigationWorkflow;
          observability?: Record<string, unknown>;
          threat_report?: Record<string, unknown>;
          entity_resolution?: Record<string, unknown> & {
            status?: string;
            message?: string;
            suggestions?: string[];
            reason?: string;
            unmatched_query?: string;
            candidates?: Array<Record<string, unknown>>;
          };
        };
      }>("investigate", {
        question: text,
        session_id: serverSessionId || undefined,
        subject: subject || {},
        provider: selectedProvider || undefined,
        model: selectedModel || undefined,
        temperature,
        max_tokens: maxTokens,
      });

      const er = data.metadata?.entity_resolution;
      const assistantMsg: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: data.answer || "(No answer)",
        citations: data.citations,
        retrieved: data.retrieved,
        confidence: data.confidence,
        intent: data.intent,
        refused: data.refused,
        model: data.model,
        kind: "investigate",
        createdAt: new Date().toISOString(),
        workflow: data.metadata?.workflow,
        observability: data.metadata?.observability,
        threatReport: parseThreatReport(data.metadata?.threat_report) ?? undefined,
        entityResolution: er
          ? {
              status: er.status || data.metadata?.status,
              message: typeof er.message === "string" ? er.message : undefined,
              suggestions: Array.isArray(er.suggestions)
                ? er.suggestions.map(String)
                : undefined,
              reason: typeof er.reason === "string" ? er.reason : undefined,
              unmatched_query:
                typeof er.unmatched_query === "string" ? er.unmatched_query : undefined,
              candidates: dedupeEntityCandidates(
                (er.candidates || []).map((c) => ({
                label: c.label != null ? String(c.label) : undefined,
                display_name:
                  c.display_name != null ? String(c.display_name) : undefined,
                username: c.username != null ? String(c.username) : undefined,
                entity_id: c.entity_id as string | number | undefined,
                entity_type: c.entity_type != null ? String(c.entity_type) : undefined,
                first_name: c.first_name != null ? String(c.first_name) : undefined,
                last_name: c.last_name != null ? String(c.last_name) : undefined,
                risk_score:
                  typeof c.risk_score === "number" ? c.risk_score : null,
                risk_level: c.risk_level != null ? String(c.risk_level) : null,
                behavior_score:
                  typeof c.behavior_score === "number" ? c.behavior_score : null,
                last_seen: c.last_seen != null ? String(c.last_seen) : null,
                chat_type: c.chat_type != null ? String(c.chat_type) : null,
                match_reason:
                  c.match_reason != null ? String(c.match_reason) : undefined,
                score: typeof c.score === "number" ? c.score : undefined,
              })),
              ),
            }
          : data.metadata?.status
            ? { status: data.metadata.status }
            : undefined,
      };
      appendExchange(sessionId, userMsg, assistantMsg, data.session_id);
      const elapsed = Math.round(performance.now() - started);
      recordAiResponseMetrics({
        latencyMs: elapsed,
        tokensEstimate: Math.max(
          32,
          Math.round((assistantMsg.content?.length || 0) / 4),
        ),
      });
      setInvestigationState({
        lastModel: data.model || getInvestigationState().lastModel || selectedModel,
        evidence: {
          citations: data.citations || [],
          retrieved: data.retrieved || [],
          confidence: data.confidence,
        },
        busy: false,
      });
    } catch (e) {
      setInvestigationState({
        error: e instanceof Error ? e.message : "Request failed",
        draft: rawText,
        busy: false,
      });
    }
  };

  const onSelectEntity = (
    candidate: import("@/components/ai/types").EntityCandidate,
    originalQuery: string,
  ) => {
    const id = candidate.entity_id;
    if (id == null) return;
    const numeric = Number(id);
    const isChat =
      candidate.entity_type === "group" ||
      candidate.entity_type === "channel" ||
      candidate.entity_type === "chat";
    const subjectOverride =
      Number.isFinite(numeric) && !Number.isNaN(numeric)
        ? isChat
          ? { chat_id: numeric }
          : { user_id: numeric }
        : undefined;
    // Re-run the original analyst question with the chosen entity bound.
    void runInvestigation(originalQuery, {
      subjectOverride,
      allowWithoutTarget: true,
    });
  };

  const onSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!draft.trim() && !entityValue.trim()) {
      showTargetRequired(activeActionId);
      return;
    }
    await runInvestigation(draft);
  };

  const onQuickAction = (actionId: string) => {
    prepareAction(actionId);
  };

  const onGenerateReport = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const subjectId = reportSubjectId.trim();
    if (!subjectId) {
      showTargetRequired("generate_report");
      return;
    }
    setInvestigationState({ busy: true, error: "" });
    const started = performance.now();
    try {
      const data = await generateReport({
        report_type: reportType,
        subject_id: subjectId,
        subject_type: reportSubjectType,
        analyst_notes: reportNotes,
        persist: true,
      });
      setInvestigationState({
        lastModel: data.model || getInvestigationState().lastModel,
        report: data,
        showReportForm: true,
        evidence: {
          citations: data.citations || [],
          retrieved: [],
          confidence: data.confidence,
        },
        busy: false,
      });
      recordAiResponseMetrics({
        latencyMs: Math.round(performance.now() - started),
        tokensEstimate: Math.max(64, Math.round((data.body_markdown?.length || 0) / 4)),
      });
    } catch (e) {
      setInvestigationState({
        error: e instanceof Error ? e.message : "Report generation failed",
        busy: false,
      });
    }
  };

  const ready =
    health?.status === "ok" ||
    (Boolean(health?.enabled) &&
      Boolean(health?.chat_configured) &&
      Boolean(health?.embeddings_configured));

  const modelLabel =
    selectedModel ||
    lastModel ||
    (selectedProvider
      ? selectedProvider
      : health?.chat_provider
        ? `${health.chat_provider}`
        : "Model —");

  const providerLabel =
    availableProviders.find((p) => p.id === selectedProvider)?.label ||
    selectedProvider ||
    health?.chat_provider ||
    "—";

  const pairs = useMemo(() => {
    if (!active) return [] as { query: string; answer: ChatMessage }[];
    const out: { query: string; answer: ChatMessage }[] = [];
    for (let i = 0; i < active.messages.length; i++) {
      const m = active.messages[i];
      if (m.role === "user") {
        const next = active.messages[i + 1];
        if (next?.role === "assistant") out.push({ query: m.content, answer: next });
      }
    }
    return out;
  }, [active]);

  if (!isClient) {
    return <div className="ai-shell" aria-busy="true" />;
  }

  return (
    <div className={`ai-shell${evidenceCollapsed ? " ai-evidence-hidden" : ""}`}>
      <ConsoleJumpNav active="ai" className="ai-rail" />

      <main className="ai-stage">
        <InvestigationHeader
          health={health}
          ready={ready}
          modelLabel={modelLabel}
          providerLabel={providerLabel}
          providerStatus={providerHealthDetail?.status}
          latencyMs={latencyMs}
          confidence={evidence.confidence}
          onRefresh={() => void refreshHealth(true)}
          onOpenSettings={() => openControlCenter("general")}
        />

        {isSim ? <SimulationBanner /> : null}

        <InvestigationWorkspaceBar
          view={view}
          onViewChange={(v) => setInvestigationState({ view: v })}
          cases={sessions}
          activeId={active?.id || null}
          onSelectCase={selectCase}
          onNewInvestigation={startNewInvestigation}
        />

        {error ? <div className="error ai-error">{error}</div> : null}

        {view === "cases" ? (
          <SavedCasesPanel sessions={sessions} onOpenCase={selectCase} />
        ) : null}

        {view === "settings" ? (
          <section className="ai-settings-panel" aria-label="Settings">
            <h2>Settings</h2>
            <div className="ai-settings-grid">
              <div className="ai-settings-card ai-settings-card-wide">
                <h3>Keys &amp; appearance</h3>
                <p className="caption">
                  Dark mode, Telegram API credentials, and OpenRouter key are managed on the shared
                  settings page (saved to <code>.env</code>).
                </p>
                <Link href="/settings" className="btn primary ai-send">
                  Open Settings
                </Link>
              </div>
              <ModelSettingsPanel onRefreshConnection={() => void refreshHealth(true)} />
              <div className="ai-settings-card">
                <h3>Appearance</h3>
                <p className="caption">Theme applies across Threat Console and Sébastien.</p>
                <ThemeToggle />
              </div>
              <div className="ai-settings-card">
                <h3>AI Control Center</h3>
                <p className="caption">
                  Advanced generation parameters, profiles, and performance tuning.
                </p>
                <button
                  type="button"
                  className="btn primary ai-send"
                  onClick={() => openControlCenter("model")}
                >
                  Open Control Center
                </button>
              </div>
              <div className="ai-settings-card">
                <h3>Connection</h3>
                <p>
                  Status: <strong>{health?.status || "offline"}</strong>
                </p>
                <p>Chat provider: {health?.chat_provider || "—"}</p>
                <p>Embedding provider: {health?.embedding_provider || "—"}</p>
                <p>Vector backend: {health?.vector_backend || "—"}</p>
                <button
                  type="button"
                  className="btn ai-btn-ghost"
                  onClick={() => void refreshHealth(true)}
                >
                  Refresh status
                </button>
              </div>
              <div className="ai-settings-card">
                <h3>Intelligence report</h3>
                <p className="caption">
                  Generate a structured report grounded in RAG evidence (
                  <code>ai_reports</code>).
                </p>
                <button
                  type="button"
                  className="btn primary ai-send"
                  onClick={() =>
                    setInvestigationState({
                      showReportForm: true,
                      view: "investigation",
                    })
                  }
                >
                  Open report form
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {view === "investigation" ? (
          <>
            <InvestigationSearch
              ref={searchRef}
              query={draft}
              onQueryChange={(value) =>
                setInvestigationState({ draft: value, targetGate: null })
              }
              placeholder={searchPlaceholder}
              actionLabel={
                QUICK_ACTIONS.find((a) => a.id === activeActionId)?.label || null
              }
              onClearAction={() =>
                setInvestigationState({
                  activeActionId: null,
                  searchPlaceholder: DEFAULT_SEARCH_PLACEHOLDER,
                })
              }
              entityKind={entityKind}
              onEntityKindChange={(kind) => setInvestigationState({ entityKind: kind })}
              entityValue={entityValue}
              onEntityValueChange={(value) => setInvestigationState({ entityValue: value })}
              busy={busy}
              onSubmit={(e) => void onSubmit(e)}
            />

            <QuickActions
              busy={busy}
              activeActionId={activeActionId}
              onAction={onQuickAction}
            />

            {showReportForm ? (
              <section className="ai-report-panel" aria-label="Report generation">
                <form className="ai-report-form" onSubmit={(e) => void onGenerateReport(e)}>
                  <label>
                    Report type
                    <select
                      value={reportType}
                      onChange={(e) => setInvestigationState({ reportType: e.target.value })}
                    >
                      {REPORT_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Subject type
                    <select
                      value={reportSubjectType}
                      onChange={(e) =>
                        setInvestigationState({ reportSubjectType: e.target.value })
                      }
                    >
                      <option value="user">User</option>
                      <option value="case">Case</option>
                      <option value="investigation">Investigation</option>
                      <option value="chat">Chat</option>
                    </select>
                  </label>
                  <label>
                    Subject ID
                    <input
                      value={reportSubjectId}
                      onChange={(e) =>
                        setInvestigationState({ reportSubjectId: e.target.value })
                      }
                      placeholder="e.g. 55"
                      required
                    />
                  </label>
                  <label className="ai-span-2">
                    Analyst notes
                    <textarea
                      value={reportNotes}
                      onChange={(e) => setInvestigationState({ reportNotes: e.target.value })}
                      rows={3}
                      placeholder="Optional context for the report prompt"
                    />
                  </label>
                  <div className="ai-span-2 ai-report-actions">
                    <button type="submit" className="btn primary" disabled={busy}>
                      {busy ? "Generating…" : "Generate report"}
                    </button>
                    <button
                      type="button"
                      className="btn ai-btn-ghost"
                      onClick={() => setInvestigationState({ showReportForm: false })}
                    >
                      Close
                    </button>
                  </div>
                </form>

                {report ? (
                  <article className="ai-report-result">
                    <div className="ai-report-result-head">
                      <h2>{report.title}</h2>
                      <span className={confidenceClass(report.confidence)}>
                        {report.confidence}
                        {report.refused ? " · refused" : ""}
                      </span>
                    </div>
                    {report.sections.map((section) => (
                      <div key={section.section_id} className="ai-report-section">
                        <h3>{section.title}</h3>
                        <p>{section.body}</p>
                      </div>
                    ))}
                  </article>
                ) : null}
              </section>
            ) : null}

            <div
              className="ai-workspace"
              ref={workspaceRef}
              aria-live="polite"
              onScroll={onWorkspaceScroll}
            >
              {targetGate ? (
                <ActionBriefPanel
                  actionId={targetGate.actionId || activeActionId || "investigate_user"}
                  onClear={() =>
                    setInvestigationState({
                      targetGate: null,
                      activeActionId: null,
                      searchPlaceholder: DEFAULT_SEARCH_PLACEHOLDER,
                      showReportForm: false,
                    })
                  }
                  onFocusSearch={() => {
                    setInvestigationState({ targetGate: null });
                    focusSearch();
                  }}
                />
              ) : null}
              {pairs.length === 0 && !busy && !targetGate ? (
                <EmptyState
                  onSelectAction={prepareAction}
                  activeActionId={activeActionId}
                />
              ) : (
                pairs.map(({ query, answer }, index) => (
                  <div key={answer.id} className="ai-result-stack">
                    <InvestigationResultCard
                      query={query}
                      message={answer}
                      busy={busy}
                      onShowEvidence={() => {
                        applyEvidence(answer.citations, answer.retrieved, answer.confidence);
                        setInvestigationState({ evidenceCollapsed: false });
                      }}
                      onSelectEntity={onSelectEntity}
                    />
                    {index === pairs.length - 1 &&
                    !busy &&
                    answer.entityResolution?.status !== "ambiguous" &&
                    answer.entityResolution?.status !== "Ambiguous Match" &&
                    answer.entityResolution?.status !== "no_match" &&
                    answer.entityResolution?.status !== "No Match Found" &&
                    answer.entityResolution?.status !== "target_required" &&
                    answer.entityResolution?.status !== "Target Required" &&
                    !answer.refused ? (
                      <SuggestedActions
                        busy={busy}
                        onAction={(prompt, actionId) => {
                          setInvestigationState({ activeActionId: actionId });
                          void runInvestigation(prompt, { allowWithoutTarget: true });
                        }}
                      />
                    ) : null}
                  </div>
                ))
              )}
              {busy ? (
                <div className="ai-working" aria-busy="true">
                  <span className="ai-typing-dot" />
                  <span className="ai-typing-dot" />
                  <span className="ai-typing-dot" />
                  <span>Analyzing evidence…</span>
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </main>

      <EvidencePanel
        citations={evidence.citations}
        retrieved={evidence.retrieved}
        confidence={evidence.confidence}
        collapsed={evidenceCollapsed}
        cardOpen={evidenceCardOpen}
        onCardOpenChange={(next) => setInvestigationState({ evidenceCardOpen: next })}
        onToggleCollapse={() =>
          setInvestigationState({ evidenceCollapsed: !getInvestigationState().evidenceCollapsed })
        }
      />

      <ControlCenterDrawer onRefreshConnection={() => void refreshHealth(true)} />
    </div>
  );
}
