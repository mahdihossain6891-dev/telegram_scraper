import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { canViewTieOpsDetail, normalizeTieRole } from "@/lib/tie-role";
import { TieOfflineError, loadTieSnapshot } from "@/services/tieService";

describe("tie-role", () => {
  it("normalizes role aliases", () => {
    expect(normalizeTieRole("Administrator")).toBe("administrator");
    expect(normalizeTieRole("senior analyst")).toBe("senior_analyst");
    expect(normalizeTieRole("Viewer")).toBe("viewer");
  });

  it("gates ops detail to senior and admin", () => {
    expect(canViewTieOpsDetail("administrator")).toBe(true);
    expect(canViewTieOpsDetail("senior_analyst")).toBe(true);
    expect(canViewTieOpsDetail("viewer")).toBe(false);
    expect(canViewTieOpsDetail("analyst")).toBe(false);
  });

  it("gates AI model config to senior and admin", async () => {
    const { canConfigureTieAi } = await import("@/lib/tie-role");
    expect(canConfigureTieAi("administrator")).toBe(true);
    expect(canConfigureTieAi("viewer")).toBe(false);
  });
});

describe("tieService.loadTieSnapshot", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-23T12:00:00Z"));
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function mockJson(path: string, body: unknown, status = 200) {
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    } as Response;
  }

  it("loads page snapshot when TIE is healthy", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/health")) {
        return mockJson(url, {
          status: "online",
          status_display: "Operational",
          version: "0.11.0",
          components: {},
        });
      }
      if (url.includes("/status")) {
        return mockJson(url, {
          status_display: "Operational",
          version: "0.11.0",
          uptime_days: 1,
          connection: "Threat Console ↔ TIE",
          ai: { provider: "Mock", model: "n/a", requests_today: 0, average_latency_ms: 0, successful_requests: 0, failed_requests: 0, token_usage: null },
          sync: { status: "Healthy", healthy: true },
          system_health: {},
        });
      }
      if (url.includes("/metrics")) {
        return mockJson(url, {
          messages_processed: 10,
          messages_today: 2,
          intelligence_reports_generated: 3,
          threats_detected: 1,
          active_campaigns: 0,
          entities_extracted: 4,
          average_processing_time_sec: 1.2,
        });
      }
      if (url.includes("/pipeline")) return mockJson(url, { stages: [] });
      if (url.includes("/recent-intelligence")) return mockJson(url, { items: [] });
      if (url.includes("/campaigns/status")) {
        return mockJson(url, {
          active_campaigns: 0,
          new_campaigns_today: 0,
          updated_campaigns: 0,
          highest_risk_campaign: null,
        });
      }
      if (url.includes("/workers")) {
        return mockJson(url, { workers: { running: 1, total: 1 }, status: "Healthy" });
      }
      if (url.includes("/queue")) {
        return mockJson(url, {
          pending_jobs: 0,
          processing_jobs: 0,
          failed_jobs: 0,
          retry_queue: 0,
          dead_letter_queue: 0,
        });
      }
      return mockJson(url, {}, 404);
    }) as typeof fetch;

    const snap = await loadTieSnapshot("administrator");
    expect(snap.offline).toBe(false);
    expect(snap.metrics?.messages_processed).toBe(10);
    expect(snap.workers?.status).toBe("Healthy");
    expect(snap.queue?.pending_jobs).toBe(0);
  });

  it("marks offline when core endpoints fail", async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch;

    const snap = await loadTieSnapshot("administrator");
    expect(snap.offline).toBe(true);
    expect(snap.metrics).toBeNull();
  });

  it("handles missing metrics without throwing", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/metrics")) return mockJson(url, {}, 500);
      if (url.includes("/health")) {
        return mockJson(url, { status: "online", status_display: "Operational", version: "0.11.0", components: {} });
      }
      if (url.includes("/status")) {
        return mockJson(url, {
          status_display: "Operational",
          version: "0.11.0",
          uptime_days: 0,
          connection: "Threat Console ↔ TIE",
          ai: { provider: "Mock", model: "n/a", requests_today: 0, average_latency_ms: 0, successful_requests: 0, failed_requests: 0, token_usage: null },
          sync: { status: "Healthy", healthy: true },
          system_health: {},
        });
      }
      if (url.includes("/pipeline")) return mockJson(url, { stages: [] });
      if (url.includes("/recent-intelligence")) return mockJson(url, { items: [] });
      if (url.includes("/campaigns/status")) {
        return mockJson(url, {
          active_campaigns: 0,
          new_campaigns_today: 0,
          updated_campaigns: 0,
          highest_risk_campaign: null,
        });
      }
      if (url.includes("/workers") || url.includes("/queue")) return mockJson(url, {}, 403);
      return mockJson(url, {}, 404);
    }) as typeof fetch;

    const snap = await loadTieSnapshot("administrator");
    expect(snap.offline).toBe(false);
    expect(snap.metrics).toBeNull();
    expect(snap.status?.status_display).toBe("Operational");
  });

  it("skips workers/queue for viewers (permission restrictions)", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/workers") || url.includes("/queue")) {
        throw new Error("should not call restricted endpoints for viewer");
      }
      if (url.includes("/health")) {
        return mockJson(url, { status: "online", status_display: "Operational", version: "0.11.0", components: {} });
      }
      if (url.includes("/status")) {
        return mockJson(url, {
          status_display: "Operational",
          version: "0.11.0",
          uptime_days: 0,
          connection: "Threat Console ↔ TIE",
          ai: { provider: "Mock", model: "n/a", requests_today: 0, average_latency_ms: 0, successful_requests: 0, failed_requests: 0, token_usage: null },
          sync: { status: "Healthy", healthy: true },
          system_health: {},
        });
      }
      if (url.includes("/metrics")) {
        return mockJson(url, {
          messages_processed: 1,
          messages_today: 0,
          intelligence_reports_generated: 0,
          threats_detected: 0,
          active_campaigns: 0,
          entities_extracted: 0,
          average_processing_time_sec: 0,
        });
      }
      if (url.includes("/pipeline")) return mockJson(url, { stages: [] });
      if (url.includes("/recent-intelligence")) return mockJson(url, { items: [] });
      if (url.includes("/campaigns/status")) {
        return mockJson(url, {
          active_campaigns: 0,
          new_campaigns_today: 0,
          updated_campaigns: 0,
          highest_risk_campaign: null,
        });
      }
      return mockJson(url, {}, 404);
    }) as typeof fetch;
    globalThis.fetch = fetchMock;

    const snap = await loadTieSnapshot("viewer");
    expect(snap.workers).toBeNull();
    expect(snap.queue).toBeNull();
    expect(snap.metrics?.messages_processed).toBe(1);
  });

  it("treats 503 as offline TIE", async () => {
    globalThis.fetch = vi.fn(async () => mockJson("/x", { error: "offline" }, 503)) as typeof fetch;
    await expect(
      (async () => {
        const { fetchTieHealth } = await import("@/services/tieService");
        await fetchTieHealth();
      })(),
    ).rejects.toBeInstanceOf(TieOfflineError);
  });
});
