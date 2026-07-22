"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";

import type {
  AiCitation,
  AiHealth,
  AiReport,
  AiRetrieved,
  Confidence,
  ConversationSession,
  DiscoveredModel,
  EntityKind,
  ProviderCatalogEntry,
  ShellView,
} from "./types";
import type { AiProfileId, ControlSectionId } from "./controlCenter/profiles";
import { GENERATION_DEFAULTS } from "./controlCenter/profiles";
import { uid } from "./utils";

const STORAGE_KEY = "sebastien.investigation.v1";
const PREFS_KEY = "sebastien.model.prefs.v1";
const HEALTH_TTL_MS = 60_000;

export type EvidenceState = {
  citations: AiCitation[];
  retrieved: AiRetrieved[];
  confidence?: Confidence;
};

export type AiPerfMetrics = {
  responseCount: number;
  totalLatencyMs: number;
  lastLatencyMs: number | null;
  totalTokensEstimate: number;
  cacheHits: number;
  cacheMisses: number;
  sessionTokensEstimate: number;
  promptVersion: string;
};

export type InvestigationState = {
  view: ShellView;
  sessions: ConversationSession[];
  activeId: string;
  draft: string;
  /** Active quick-action intent (setup only — does not start investigation). */
  activeActionId: string | null;
  searchPlaceholder: string;
  /** Client-side gate when analyst tries to investigate without a target. */
  targetGate: {
    title: string;
    message: string;
    actionId?: string | null;
  } | null;
  entityKind: EntityKind | null;
  entityValue: string;
  evidence: EvidenceState;
  evidenceCollapsed: boolean;
  evidenceCardOpen: Record<string, boolean>;
  report: AiReport | null;
  reportType: string;
  reportSubjectId: string;
  reportSubjectType: string;
  reportNotes: string;
  showReportForm: boolean;
  latencyMs: number | null;
  lastModel: string;
  health: AiHealth | null;
  healthFetchedAt: number;
  workspaceScrollTop: number;
  error: string;
  busy: boolean;
  /** Persisted Sebastian model-selection preferences. */
  selectedProvider: string;
  selectedModel: string;
  temperature: number;
  topP: number;
  maxTokens: number;
  preferStreaming: boolean;
  stopSequences: string;
  aiProfile: AiProfileId;
  availableProviders: ProviderCatalogEntry[];
  availableModels: DiscoveredModel[];
  modelsLoading: boolean;
  modelsError: string;
  providerHealthDetail: ProviderCatalogEntry["health"] | null;
  modelsLastRefreshAt: number;
  /** AI Control Center drawer (Phase 3) — independent of investigation view. */
  controlCenterOpen: boolean;
  controlCenterSection: ControlSectionId;
  controlCenterScrollTop: number;
  perfMetrics: AiPerfMetrics;
};

type Listener = () => void;

export function isActiveCase(session: ConversationSession): boolean {
  return (session.status || "active") !== "dismissed";
}

export function selectActiveCases(sessions: ConversationSession[]): ConversationSession[] {
  return sessions.filter(isActiveCase);
}

export function selectDismissedCases(sessions: ConversationSession[]): ConversationSession[] {
  return sessions.filter((s) => !isActiveCase(s));
}

export function createEmptyCase(): ConversationSession {
  const now = new Date().toISOString();
  return {
    id: uid(),
    title: "New Investigation",
    mode: "investigate",
    serverSessionId: null,
    messages: [],
    updatedAt: now,
    description: "Awaiting first query",
    risk: "unknown",
    status: "active",
    dismissedAt: null,
  };
}

function normalizeSession(session: ConversationSession): ConversationSession {
  return {
    ...session,
    status: session.status || "active",
    dismissedAt: session.dismissedAt ?? null,
  };
}

/** Stable SSR snapshot — avoids hydration mismatch with sessionStorage. */
const SERVER_BOOT: InvestigationState = {
  view: "investigation",
  sessions: [
    {
      id: "boot",
      title: "New Investigation",
      mode: "investigate",
      serverSessionId: null,
      messages: [],
      updatedAt: "1970-01-01T00:00:00.000Z",
      description: "Awaiting first query",
      risk: "unknown",
      status: "active",
      dismissedAt: null,
    },
  ],
  activeId: "boot",
  draft: "",
  activeActionId: null,
  searchPlaceholder:
    "Investigate a user, group, message, wallet, phone number, or suspicious activity...",
  targetGate: null,
  entityKind: null,
  entityValue: "",
  evidence: { citations: [], retrieved: [] },
  evidenceCollapsed: false,
  evidenceCardOpen: {},
  report: null,
  reportType: "user_intelligence",
  reportSubjectId: "",
  reportSubjectType: "user",
  reportNotes: "",
  showReportForm: false,
  latencyMs: null,
  lastModel: "",
  health: null,
  healthFetchedAt: 0,
  workspaceScrollTop: 0,
  error: "",
  busy: false,
  selectedProvider: "",
  selectedModel: "",
  temperature: GENERATION_DEFAULTS.temperature,
  topP: GENERATION_DEFAULTS.topP,
  maxTokens: GENERATION_DEFAULTS.maxTokens,
  preferStreaming: GENERATION_DEFAULTS.preferStreaming,
  stopSequences: GENERATION_DEFAULTS.stopSequences,
  aiProfile: "balanced",
  availableProviders: [],
  availableModels: [],
  modelsLoading: false,
  modelsError: "",
  providerHealthDetail: null,
  modelsLastRefreshAt: 0,
  controlCenterOpen: false,
  controlCenterSection: "general",
  controlCenterScrollTop: 0,
  perfMetrics: {
    responseCount: 0,
    totalLatencyMs: 0,
    lastLatencyMs: null,
    totalTokensEstimate: 0,
    cacheHits: 0,
    cacheMisses: 0,
    sessionTokensEstimate: 0,
    promptVersion: "investigation_assistant@v1",
  },
};

function freshClientState(): InvestigationState {
  const first = createEmptyCase();
  const prefs = loadModelPrefs();
  return {
    ...SERVER_BOOT,
    sessions: [first],
    activeId: first.id,
    selectedProvider: prefs.selectedProvider || "",
    selectedModel: prefs.selectedModel || "",
    temperature:
      typeof prefs.temperature === "number" ? prefs.temperature : SERVER_BOOT.temperature,
    topP: typeof prefs.topP === "number" ? prefs.topP : SERVER_BOOT.topP,
    maxTokens: typeof prefs.maxTokens === "number" ? prefs.maxTokens : SERVER_BOOT.maxTokens,
    preferStreaming:
      typeof prefs.preferStreaming === "boolean"
        ? prefs.preferStreaming
        : SERVER_BOOT.preferStreaming,
    stopSequences:
      typeof prefs.stopSequences === "string" ? prefs.stopSequences : SERVER_BOOT.stopSequences,
    aiProfile: prefs.aiProfile || SERVER_BOOT.aiProfile,
  };
}

function loadModelPrefs(): Partial<InvestigationState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Partial<InvestigationState>;
    return {
      selectedProvider:
        typeof parsed.selectedProvider === "string" ? parsed.selectedProvider : "",
      selectedModel: typeof parsed.selectedModel === "string" ? parsed.selectedModel : "",
      temperature:
        typeof parsed.temperature === "number" ? parsed.temperature : undefined,
      topP: typeof parsed.topP === "number" ? parsed.topP : undefined,
      maxTokens: typeof parsed.maxTokens === "number" ? parsed.maxTokens : undefined,
      preferStreaming:
        typeof parsed.preferStreaming === "boolean" ? parsed.preferStreaming : undefined,
      stopSequences:
        typeof parsed.stopSequences === "string" ? parsed.stopSequences : undefined,
      aiProfile:
        parsed.aiProfile === "fast" ||
        parsed.aiProfile === "balanced" ||
        parsed.aiProfile === "deep" ||
        parsed.aiProfile === "custom"
          ? parsed.aiProfile
          : undefined,
    };
  } catch {
    return {};
  }
}

function saveModelPrefs(state: InvestigationState) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      PREFS_KEY,
      JSON.stringify({
        selectedProvider: state.selectedProvider,
        selectedModel: state.selectedModel,
        temperature: state.temperature,
        topP: state.topP,
        maxTokens: state.maxTokens,
        preferStreaming: state.preferStreaming,
        stopSequences: state.stopSequences,
        aiProfile: state.aiProfile,
      }),
    );
  } catch {
    // Quota / private mode — keep in-memory only.
  }
}

function toPersisted(state: InvestigationState): Omit<
  InvestigationState,
  | "busy"
  | "error"
  | "modelsLoading"
  | "modelsError"
  | "availableProviders"
  | "availableModels"
  | "providerHealthDetail"
  | "controlCenterOpen"
> {
  const {
    busy: _b,
    error: _e,
    modelsLoading: _ml,
    modelsError: _me,
    availableProviders: _ap,
    availableModels: _am,
    providerHealthDetail: _ph,
    controlCenterOpen: _cc,
    ...rest
  } = state;
  return rest;
}

function loadPersisted(): InvestigationState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<InvestigationState>;
    if (!parsed.sessions || !Array.isArray(parsed.sessions) || parsed.sessions.length === 0) {
      return null;
    }
    const sessions = parsed.sessions.map(normalizeSession);
    const activeSessions = selectActiveCases(sessions);
    let activeId = parsed.activeId || "";
    if (!activeId || !activeSessions.some((s) => s.id === activeId)) {
      activeId = activeSessions[0]?.id || "";
    }
    if (!activeId) {
      const blank = createEmptyCase();
      sessions.push(blank);
      activeId = blank.id;
    }
    const prefs = loadModelPrefs();
    return {
      ...SERVER_BOOT,
      ...parsed,
      sessions,
      activeId,
      busy: false,
      error: "",
      evidence: parsed.evidence || { citations: [], retrieved: [] },
      evidenceCardOpen: parsed.evidenceCardOpen || {},
      selectedProvider: prefs.selectedProvider || parsed.selectedProvider || "",
      selectedModel: prefs.selectedModel || parsed.selectedModel || "",
      temperature:
        typeof prefs.temperature === "number"
          ? prefs.temperature
          : typeof parsed.temperature === "number"
            ? parsed.temperature
            : SERVER_BOOT.temperature,
      topP:
        typeof prefs.topP === "number"
          ? prefs.topP
          : typeof parsed.topP === "number"
            ? parsed.topP
            : SERVER_BOOT.topP,
      maxTokens:
        typeof prefs.maxTokens === "number"
          ? prefs.maxTokens
          : typeof parsed.maxTokens === "number"
            ? parsed.maxTokens
            : SERVER_BOOT.maxTokens,
      preferStreaming:
        typeof prefs.preferStreaming === "boolean"
          ? prefs.preferStreaming
          : typeof parsed.preferStreaming === "boolean"
            ? parsed.preferStreaming
            : SERVER_BOOT.preferStreaming,
      stopSequences:
        typeof prefs.stopSequences === "string"
          ? prefs.stopSequences
          : typeof parsed.stopSequences === "string"
            ? parsed.stopSequences
            : SERVER_BOOT.stopSequences,
      aiProfile: prefs.aiProfile || parsed.aiProfile || SERVER_BOOT.aiProfile,
      availableProviders: [],
      availableModels: [],
      modelsLoading: false,
      modelsError: "",
      providerHealthDetail: null,
      controlCenterOpen: false,
      controlCenterSection: parsed.controlCenterSection || SERVER_BOOT.controlCenterSection,
      controlCenterScrollTop: parsed.controlCenterScrollTop || 0,
      perfMetrics: {
        ...SERVER_BOOT.perfMetrics,
        ...(parsed.perfMetrics || {}),
      },
      modelsLastRefreshAt: parsed.modelsLastRefreshAt || 0,
    };
  } catch {
    return null;
  }
}

function savePersisted(next: InvestigationState) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toPersisted(next)));
  } catch {
    // Quota / private mode — keep in-memory only.
  }
  saveModelPrefs(next);
}

let state: InvestigationState = SERVER_BOOT;
let hydrated = false;
const listeners = new Set<Listener>();

function hydrateOnce() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;
  state = loadPersisted() || freshClientState();
}

function emit() {
  savePersisted(state);
  listeners.forEach((l) => l());
}

export function getInvestigationState(): InvestigationState {
  hydrateOnce();
  return state;
}

export function setInvestigationState(
  patch: Partial<InvestigationState> | ((prev: InvestigationState) => Partial<InvestigationState>),
) {
  hydrateOnce();
  const nextPatch = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...nextPatch };
  emit();
}

export function updateInvestigationState(updater: (prev: InvestigationState) => InvestigationState) {
  hydrateOnce();
  state = updater(state);
  emit();
}

/**
 * Soft-dismiss a case in client state. Keeps the record for future Archived Cases.
 * Returns the next active case id (may be a newly created blank case).
 */
export function dismissCaseLocally(caseId: string): string {
  let nextActiveId = "";
  updateInvestigationState((prev) => {
    const now = new Date().toISOString();
    const sessions = prev.sessions.map((s) =>
      s.id === caseId
        ? { ...s, status: "dismissed" as const, dismissedAt: now, updatedAt: now }
        : s,
    );
    const remaining = selectActiveCases(sessions);
    let activeId = prev.activeId;
    let nextSessions = sessions;
    let evidence = prev.evidence;
    let draft = prev.draft;
    let showReportForm = prev.showReportForm;
    let report = prev.report;

    if (activeId === caseId || !remaining.some((s) => s.id === activeId)) {
      if (remaining.length > 0) {
        activeId = remaining[0].id;
        const last = [...remaining[0].messages].reverse().find((m) => m.role === "assistant");
        evidence = last
          ? {
              citations: last.citations || [],
              retrieved: last.retrieved || [],
              confidence: last.confidence,
            }
          : { citations: [], retrieved: [] };
      } else {
        const blank = createEmptyCase();
        nextSessions = [...sessions, blank];
        activeId = blank.id;
        evidence = { citations: [], retrieved: [] };
        draft = "";
        showReportForm = false;
        report = null;
      }
    }

    nextActiveId = activeId;
    return {
      ...prev,
      sessions: nextSessions,
      activeId,
      evidence,
      draft,
      showReportForm,
      report,
      view: "investigation",
      workspaceScrollTop: 0,
      error: "",
    };
  });
  return nextActiveId;
}

export function renameCaseLocally(caseId: string, title: string): void {
  const trimmed = title.trim();
  if (!trimmed) return;
  updateInvestigationState((prev) => ({
    ...prev,
    sessions: prev.sessions.map((s) =>
      s.id === caseId
        ? { ...s, title: trimmed.slice(0, 120), updatedAt: new Date().toISOString() }
        : s,
    ),
  }));
}

export function subscribeInvestigation(listener: Listener): () => void {
  hydrateOnce();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function healthIsFresh(st: InvestigationState = state): boolean {
  return Boolean(st.health) && Date.now() - st.healthFetchedAt < HEALTH_TTL_MS;
}

/** Record client-side latency / token estimates after an AI turn (never clears cases). */
export function recordAiResponseMetrics(opts: {
  latencyMs: number;
  tokensEstimate?: number;
  cacheHit?: boolean;
}) {
  updateInvestigationState((prev) => {
    const tokens = Math.max(0, opts.tokensEstimate ?? Math.round(opts.latencyMs / 4));
    const hits = prev.perfMetrics.cacheHits + (opts.cacheHit ? 1 : 0);
    const misses = prev.perfMetrics.cacheMisses + (opts.cacheHit ? 0 : 1);
    return {
      ...prev,
      latencyMs: opts.latencyMs,
      perfMetrics: {
        ...prev.perfMetrics,
        responseCount: prev.perfMetrics.responseCount + 1,
        totalLatencyMs: prev.perfMetrics.totalLatencyMs + opts.latencyMs,
        lastLatencyMs: opts.latencyMs,
        totalTokensEstimate: prev.perfMetrics.totalTokensEstimate + tokens,
        sessionTokensEstimate: prev.perfMetrics.sessionTokensEstimate + tokens,
        cacheHits: hits,
        cacheMisses: misses,
      },
    };
  });
}

export function openControlCenter(section?: ControlSectionId) {
  setInvestigationState({
    controlCenterOpen: true,
    ...(section ? { controlCenterSection: section } : {}),
  });
}

export function closeControlCenter() {
  setInvestigationState({ controlCenterOpen: false });
}

/** True after client mount — use to avoid SSR/sessionStorage mismatch flash. */
export function useIsClient(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

/**
 * Subscribe to the investigation store. Optional selector reduces re-renders.
 */
export function useInvestigationStore(): InvestigationState;
export function useInvestigationStore<T>(selector: (s: InvestigationState) => T): T;
export function useInvestigationStore<T>(
  selector?: (s: InvestigationState) => T,
): InvestigationState | T {
  const selectorRef = useRef(selector);
  selectorRef.current = selector;

  const getSnapshot = useCallback(() => {
    const s = getInvestigationState();
    return selectorRef.current ? selectorRef.current(s) : s;
  }, []);

  const getServerSnapshot = useCallback(() => {
    return selectorRef.current ? selectorRef.current(SERVER_BOOT) : SERVER_BOOT;
  }, []);

  return useSyncExternalStore(subscribeInvestigation, getSnapshot, getServerSnapshot);
}
