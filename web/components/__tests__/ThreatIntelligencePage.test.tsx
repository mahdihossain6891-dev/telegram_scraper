/**
 * @vitest-environment jsdom
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThreatIntelligencePage } from "@/components/ThreatIntelligencePage";
import type { TieSnapshot } from "@/lib/tie-types";

const baseSnap = (over: Partial<TieSnapshot> = {}): TieSnapshot => ({
  health: {
    service: "Threat Intelligence Engine",
    status: "online",
    status_display: "Operational",
    version: "0.11.0",
    components: {
      database: { status: "Healthy" },
      redis: { status: "Healthy" },
      workers: { status: "Healthy" },
      llm_provider: { status: "Healthy" },
      threat_console_sync: { status: "Healthy" },
    },
  },
  status: {
    service: "Threat Intelligence Engine",
    status: "online",
    status_display: "Operational",
    version: "0.11.0",
    uptime_seconds: 86400,
    uptime_days: 1,
    connection: "Threat Console ↔ TIE",
    ai: {
      provider: "Mock",
      model: "n/a",
      requests_today: 12,
      average_latency_ms: 40,
      successful_requests: 12,
      failed_requests: 0,
      token_usage: null,
    },
    sync: { status: "Healthy", healthy: true },
    system_health: {
      database: { status: "Healthy" },
      redis: { status: "Healthy" },
      workers: { status: "Healthy" },
      llm_provider: { status: "Healthy" },
      threat_console_sync: { status: "Healthy" },
    },
  },
  metrics: {
    messages_processed: 125430,
    messages_today: 10,
    intelligence_reports_generated: 4820,
    threats_detected: 932,
    active_campaigns: 27,
    entities_extracted: 18450,
    average_processing_time_sec: 1.4,
  },
  pipeline: {
    stages: [
      {
        id: "telegram_scraper",
        name: "Telegram Scraper",
        status: "Healthy",
        last_processed_at: "2026-07-23T11:59:00Z",
        current_workload: "Inbound",
      },
    ],
  },
  workers: { workers: { running: 1, total: 1 }, status: "Healthy" },
  queue: {
    pending_jobs: 0,
    processing_jobs: 1,
    failed_jobs: 0,
    retry_queue: 0,
    dead_letter_queue: 0,
  },
  recent: [
    {
      id: "10293",
      title: "Threat Report #10293",
      category: "Fraud",
      risk: "High",
      confidence: 91,
      generated_at: "2026-07-23T11:58:00Z",
    },
  ],
  campaigns: {
    active_campaigns: 27,
    new_campaigns_today: 5,
    updated_campaigns: 12,
    highest_risk_campaign: {
      campaign_id: "camp-1",
      category: "Fraud",
      risk_score: 92,
    },
  },
  offline: false,
  lastSuccessAt: "2026-07-23T12:00:00Z",
  errors: [],
  ...over,
});

vi.mock("@/services/tieService", () => ({
  loadTieSnapshot: vi.fn(),
  fetchTieAiConfig: vi.fn(),
  fetchTieAiModels: vi.fn(),
  updateTieAiConfig: vi.fn(),
  fetchTieProcessStatus: vi.fn(),
  startTieProcess: vi.fn(),
  stopTieProcess: vi.fn(),
}));

vi.mock("@/components/mode/TieEngineProvider", () => ({
  useTieEngine: vi.fn(),
}));

import {
  fetchTieAiConfig,
  fetchTieProcessStatus,
  loadTieSnapshot,
  startTieProcess,
  updateTieAiConfig,
} from "@/services/tieService";
import { useTieEngine } from "@/components/mode/TieEngineProvider";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ThreatIntelligencePage", () => {
  beforeEach(() => {
    vi.mocked(useTieEngine).mockReturnValue({
      enabled: true,
      analyser: "tie",
      description: "TIE processes scrape intelligence",
      busy: false,
      error: null,
      refresh: vi.fn(),
      setEnabled: vi.fn(),
    });
    vi.mocked(fetchTieProcessStatus).mockResolvedValue({
      running: false,
      healthy: false,
      configured: true,
      cwd: "C:\\Users\\mahdi\\threat translation engine",
      url: "http://127.0.0.1:8000",
    });
    vi.mocked(startTieProcess).mockResolvedValue({
      ok: true,
      started: true,
      running: true,
      healthy: true,
      configured: true,
    });
    vi.mocked(fetchTieAiConfig).mockResolvedValue({
      provider: "mock",
      model: "mock",
      detection_enabled: true,
      has_api_key: false,
      providers: [
        { id: "mock", label: "Mock" },
        { id: "openai", label: "OpenAI / OpenRouter" },
        { id: "local", label: "Local LLM" },
      ],
      models: [{ id: "mock", label: "Mock (heuristic)" }],
    });
  });

  it("loads operational status and metrics", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap());
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => {
      expect(screen.getByText("Operational")).toBeTruthy();
    });
    expect(screen.getByText("125,430")).toBeTruthy();
    expect(screen.getByText("Threat Report #10293")).toBeTruthy();
    expect(screen.getByText("Queue and worker status")).toBeTruthy();
    expect(screen.getByText("Pending jobs")).toBeTruthy();
  });

  it("shows AI model picker for administrators", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap());
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => {
      expect(screen.getByLabelText("TIE AI provider")).toBeTruthy();
    });
    expect(screen.getByRole("button", { name: "Apply model" })).toBeTruthy();
  });

  it("hides AI model controls for viewers", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap({ workers: null, queue: null }));
    render(<ThreatIntelligencePage role="viewer" />);
    await waitFor(() => {
      expect(screen.getByText("Operational")).toBeTruthy();
    });
    expect(screen.queryByLabelText("TIE AI provider")).toBeNull();
    expect(screen.getByText(/Model selection requires Senior Analyst/)).toBeTruthy();
  });

  it("applies AI model selection", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap());
    vi.mocked(updateTieAiConfig).mockResolvedValue({
      provider: "openai",
      model: "gpt-4o-mini",
      detection_enabled: true,
      has_api_key: true,
      providers: [
        { id: "mock", label: "Mock" },
        { id: "openai", label: "OpenAI / OpenRouter" },
      ],
      models: [{ id: "gpt-4o-mini", label: "GPT-4o mini" }],
    });
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => expect(screen.getByLabelText("TIE AI provider")).toBeTruthy());
    screen.getByRole("button", { name: "Apply model" }).click();
    await waitFor(() => {
      expect(updateTieAiConfig).toHaveBeenCalled();
    });
  });

  it("shows built-in analyser when TIE is off", async () => {
    vi.mocked(useTieEngine).mockReturnValue({
      enabled: false,
      analyser: "console_builtin",
      description: "Threat Console built-in scrape analyser",
      busy: false,
      error: null,
      refresh: vi.fn(),
      setEnabled: vi.fn(),
    });
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => {
      expect(screen.getByText("Built-in Console analyser active")).toBeTruthy();
    });
    expect(screen.getAllByRole("button", { name: "Start Engine" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Stop Engine" })).toBeTruthy();
    expect(loadTieSnapshot).not.toHaveBeenCalled();
  });

  it("shows offline state with start engine and retry", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(
      baseSnap({
        offline: true,
        health: null,
        status: null,
        metrics: null,
        pipeline: null,
        workers: null,
        queue: null,
        recent: [],
        campaigns: null,
        lastSuccessAt: null,
      }),
    );
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => {
      expect(screen.getByText("Threat Intelligence Engine Offline")).toBeTruthy();
    });
    expect(screen.getAllByRole("button", { name: "Start Engine" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("hides queue details for viewers", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(
      baseSnap({ workers: null, queue: null }),
    );
    render(<ThreatIntelligencePage role="viewer" />);
    await waitFor(() => {
      expect(screen.getByText("Operational")).toBeTruthy();
    });
    expect(screen.getByText(/Restricted — Senior Analyst/)).toBeTruthy();
    expect(screen.queryByText("Pending jobs")).toBeNull();
  });

  it("supports auto-refresh controls", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap());
    render(<ThreatIntelligencePage role="administrator" refreshSeconds={30} />);
    await waitFor(() => {
      expect(screen.getByLabelText("TIE refresh interval seconds")).toBeTruthy();
    });
    const checkbox = screen.getByLabelText("Auto-refresh") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("renders under dark and light theme roots", async () => {
    vi.mocked(loadTieSnapshot).mockResolvedValue(baseSnap());
    document.documentElement.setAttribute("data-theme", "dark");
    const { unmount } = render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => expect(screen.getByText("Operational")).toBeTruthy());
    unmount();
    document.documentElement.setAttribute("data-theme", "light");
    render(<ThreatIntelligencePage role="administrator" />);
    await waitFor(() => expect(screen.getByText("Operational")).toBeTruthy());
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
