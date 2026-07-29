/**
 * Threat Intelligence Engine (TIE) client for Threat Console.
 * Consumes TIE HTTP APIs only — never talks to the TIE database.
 */

import { canViewTieOpsDetail, type TieConsoleRole } from "@/lib/tie-role";
import type {
  TieCampaignStatus,
  TieAiConfig,
  TieHealth,
  TieMetrics,
  TiePipeline,
  TieQueue,
  TieRecentItem,
  TieSnapshot,
  TieStatus,
  TieWorkers,
} from "@/lib/tie-types";

export class TieOfflineError extends Error {
  constructor(message = "Threat Intelligence Engine Offline") {
    super(message);
    this.name = "TieOfflineError";
  }
}

async function tieFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const suffix = path.replace(/^\//, "");
  let response: Response;
  try {
    response = await fetch(`/api/tie/${suffix}`, {
      cache: "no-store",
      ...init,
    });
  } catch {
    throw new TieOfflineError();
  }

  if (response.status === 503 || response.status === 502) {
    throw new TieOfflineError();
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    let detail = text;
    try {
      const body = JSON.parse(text);
      detail = body?.detail?.message || body?.error || text;
    } catch {
      /* keep text */
    }
    const err = new Error(detail || `TIE request failed (${response.status})`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }

  return (await response.json()) as T;
}

export async function fetchTieHealth(): Promise<TieHealth> {
  return tieFetch<TieHealth>("health");
}

export async function fetchTieStatus(): Promise<TieStatus> {
  return tieFetch<TieStatus>("status");
}

export async function fetchTieMetrics(): Promise<TieMetrics> {
  return tieFetch<TieMetrics>("metrics");
}

export async function fetchTiePipeline(): Promise<TiePipeline> {
  return tieFetch<TiePipeline>("pipeline");
}

export async function fetchTieWorkers(): Promise<TieWorkers> {
  return tieFetch<TieWorkers>("workers");
}

export async function fetchTieQueue(): Promise<TieQueue> {
  return tieFetch<TieQueue>("queue");
}

export async function fetchTieRecentIntelligence(limit = 10): Promise<TieRecentItem[]> {
  const body = await tieFetch<{ items: TieRecentItem[] }>(`recent-intelligence?limit=${limit}`);
  return body.items || [];
}

export async function fetchTieCampaignStatus(): Promise<TieCampaignStatus> {
  return tieFetch<TieCampaignStatus>("campaigns/status");
}

export async function fetchTieAiConfig(): Promise<TieAiConfig> {
  return tieFetch<TieAiConfig>("ai-config");
}

export async function fetchTieAiModels(provider: string): Promise<TieAiConfig["models"]> {
  const body = await tieFetch<{ models: TieAiConfig["models"] }>(
    `ai-models?provider=${encodeURIComponent(provider)}`,
  );
  return body.models || [];
}

export async function updateTieAiConfig(input: {
  provider: string;
  model: string;
  detection_enabled?: boolean;
  persist?: boolean;
}): Promise<TieAiConfig> {
  return tieFetch<TieAiConfig>("ai-config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: input.provider,
      model: input.model,
      detection_enabled: input.detection_enabled,
      persist: input.persist ?? true,
    }),
  });
}

export type TieProcessStatus = {
  ok?: boolean;
  running: boolean;
  managed?: boolean;
  healthy: boolean;
  configured?: boolean;
  pid?: number | null;
  port?: number;
  url?: string;
  cwd?: string | null;
  started?: boolean;
  stopped?: boolean;
  detail?: string;
  error?: string;
  mode?: {
    enabled?: boolean;
    analyser?: string;
    description?: string;
    updated_at?: string | null;
  };
};

async function processFetch(path: string, method: "GET" | "POST" = "GET"): Promise<TieProcessStatus> {
  const res = await fetch(`/api/tie-engine/process${path}`, {
    method,
    cache: "no-store",
  });
  const body = (await res.json().catch(() => ({}))) as TieProcessStatus;
  if (!res.ok) {
    throw new Error(body.error || `TIE process request failed (${res.status})`);
  }
  return {
    running: Boolean(body.running),
    healthy: Boolean(body.healthy),
    ...body,
  };
}

export async function fetchTieProcessStatus(): Promise<TieProcessStatus> {
  return processFetch("");
}

export async function startTieProcess(): Promise<TieProcessStatus> {
  return processFetch("/start", "POST");
}

export async function stopTieProcess(): Promise<TieProcessStatus> {
  return processFetch("/stop", "POST");
}

/**
 * Load a full ops snapshot. Viewer/analyst skip workers + queue (403 expected).
 * Partial failures do not throw unless every core call fails (offline).
 */
export async function loadTieSnapshot(role: TieConsoleRole): Promise<TieSnapshot> {
  const errors: string[] = [];
  let offline = false;
  let lastSuccessAt: string | null = null;

  async function one<T>(label: string, fn: () => Promise<T>): Promise<T | null> {
    try {
      const value = await fn();
      lastSuccessAt = new Date().toISOString();
      return value;
    } catch (err) {
      if (err instanceof TieOfflineError) {
        offline = true;
        errors.push(label + ": offline");
      } else {
        const status = (err as Error & { status?: number }).status;
        if (status === 403) {
          errors.push(label + ": forbidden");
        } else {
          errors.push(label + ": " + (err instanceof Error ? err.message : "failed"));
        }
      }
      return null;
    }
  }

  const [health, status, metrics, pipeline, recent, campaigns] = await Promise.all([
    one("health", fetchTieHealth),
    one("status", fetchTieStatus),
    one("metrics", fetchTieMetrics),
    one("pipeline", fetchTiePipeline),
    one("recent", () => fetchTieRecentIntelligence(10)),
    one("campaigns", fetchTieCampaignStatus),
  ]);

  let workers: TieWorkers | null = null;
  let queue: TieQueue | null = null;
  if (canViewTieOpsDetail(role)) {
    workers = await one("workers", fetchTieWorkers);
    queue = await one("queue", fetchTieQueue);
  }

  const coreFailed = !health && !status && !metrics;
  if (coreFailed) {
    offline = true;
  }

  return {
    health,
    status,
    metrics,
    pipeline,
    workers,
    queue,
    recent: recent || [],
    campaigns,
    offline,
    lastSuccessAt,
    errors,
  };
}

export const tieService = {
  fetchTieHealth,
  fetchTieStatus,
  fetchTieMetrics,
  fetchTiePipeline,
  fetchTieWorkers,
  fetchTieQueue,
  fetchTieRecentIntelligence,
  fetchTieCampaignStatus,
  fetchTieAiConfig,
  fetchTieAiModels,
  updateTieAiConfig,
  fetchTieProcessStatus,
  startTieProcess,
  stopTieProcess,
  loadTieSnapshot,
  TieOfflineError,
};
