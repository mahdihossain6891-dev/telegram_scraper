import type {
  AiHealth,
  AiReport,
  ModelsResponse,
  ProviderHealthSnapshot,
  ProvidersResponse,
} from "./types";

function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const record = body as Record<string, unknown>;
  if (typeof record.error === "string") return record.error;
  const detail = record.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const msg = (detail as { message?: unknown }).message;
    if (typeof msg === "string") return msg;
  }
  return fallback;
}

export async function fetchAiHealth(): Promise<AiHealth> {
  const res = await fetch("/api/ai/health", { cache: "no-store" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(body, "AI health check failed"));
  return body as AiHealth;
}

export async function fetchAiProviders(refresh = false): Promise<ProvidersResponse> {
  const qs = refresh ? "?refresh=true" : "";
  const res = await fetch(`/api/ai/providers${qs}`, { cache: "no-store" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(body, "Failed to load providers"));
  return body as ProvidersResponse;
}

export async function fetchAiModels(
  provider?: string | null,
  refresh = false,
): Promise<ModelsResponse> {
  const params = new URLSearchParams();
  if (provider) params.set("provider", provider);
  if (refresh) params.set("refresh", "true");
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`/api/ai/models${qs}`, { cache: "no-store" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(body, "Failed to load models"));
  return body as ModelsResponse;
}

export async function fetchProviderHealth(
  provider?: string | null,
  refresh = false,
): Promise<ProviderHealthSnapshot & { provider?: string }> {
  const params = new URLSearchParams();
  if (provider) params.set("provider", provider);
  if (refresh) params.set("refresh", "true");
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`/api/ai/provider/health${qs}`, { cache: "no-store" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(body, "Provider health check failed"));
  return body as ProviderHealthSnapshot & { provider?: string };
}

export async function postAi<T = Record<string, unknown>>(
  path: string,
  payload: Record<string, unknown>,
): Promise<T> {
  const res = await fetch(`/api/ai/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(body, `AI ${path} failed`));
  return body as T;
}

export async function generateReport(
  payload: Record<string, unknown>,
): Promise<AiReport> {
  return postAi<AiReport>("report", payload);
}

/** Soft-dismiss a server ``ai_sessions`` record. Never deletes intel data. */
export async function dismissServerSession(sessionId: string): Promise<void> {
  await postAi("session/dismiss", { session_id: sessionId });
}

export async function clearAiCache(provider?: string | null): Promise<{ ok: boolean }> {
  return postAi("cache/clear", provider ? { provider } : {});
}

export async function testAiProvider(
  provider?: string | null,
): Promise<{
  ok: boolean;
  status?: string;
  detail?: string;
  latency_ms?: number | null;
  models_available?: number | null;
  provider?: string;
}> {
  return postAi("provider/test", provider ? { provider } : {});
}

export async function reloadPromptTemplates(): Promise<{
  ok: boolean;
  prompt_ids?: string[];
  prompt_version?: string;
}> {
  return postAi("prompts/reload", {});
}
