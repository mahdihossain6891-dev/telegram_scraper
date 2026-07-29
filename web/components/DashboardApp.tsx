"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { AnalyticsPage } from "@/components/AnalyticsPage";
import { CasesPage } from "@/components/CasesPage";
import { CommandPage } from "@/components/CommandPage";
import { IntelPage } from "@/components/IntelPage";
import { AppNavbar } from "@/components/layout/AppNavbar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { parseDashboardPage } from "@/lib/console-nav";
import { SimulationBanner } from "@/components/mode/SimulationBanner";
import { useDataMode } from "@/components/mode/DataModeProvider";
import { ScrapeControl } from "@/components/ScrapeControl";
import { OpsPage } from "@/components/OpsPage";
import { SourcesPage } from "@/components/SourcesPage";
import { ThreatSimulationPage } from "@/components/ThreatSimulationPage";
import { type PageName } from "@/lib/constants";
import {
  buildExportDashboard,
  collectionBreakdown,
  defaultFilters,
  filterChatSummaries,
  filterEntities,
  filterMessages,
  timestampBounds,
} from "@/lib/dashboard-data";
import { buildPersonnelFromPayload } from "@/lib/personnel";
import { enrichPersonnelRisk, riskSummary } from "@/lib/risk";
import type { DashboardFilters, ExportPayload } from "@/lib/types";

type DashboardAppProps = {
  source: string;
  payload: ExportPayload;
  autoRefresh?: boolean;
  refreshSeconds?: number;
  lastFetchedAt?: string;
  onAutoRefreshChange?: (enabled: boolean) => void;
  onRefreshSecondsChange?: (seconds: number) => void;
  onManualRefresh?: () => void;
};

export function DashboardApp({
  source,
  payload,
  autoRefresh = false,
  refreshSeconds = 30,
  lastFetchedAt = "",
  onAutoRefreshChange,
  onRefreshSecondsChange,
  onManualRefresh,
}: DashboardAppProps) {
  const { mode, simulation } = useDataMode();
  const isSim = mode === "simulation" && simulation.simulation_active;
  const data = useMemo(() => buildExportDashboard(payload), [payload]);
  const allChatIds = useMemo(
    () => data.chatSummaries.map((row) => row.chat_id),
    [data.chatSummaries],
  );
  const chatIdsKey = allChatIds.join(",");
  const [page, setPage] = useState<PageName>("Command");
  const [filters, setFilters] = useState<DashboardFilters>(() => defaultFilters(allChatIds));
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // When live ↔ simulation swaps (or a new scrape lands), chat IDs change.
  // Reset scope so pages aren't filtered to the previous dataset's empty set.
  useEffect(() => {
    setFilters(defaultFilters(allChatIds));
  }, [mode, simulation.simulation_active, simulation.session_id, source, chatIdsKey, allChatIds]);

  useEffect(() => {
    const next = parseDashboardPage(new URLSearchParams(window.location.search).get("page"));
    if (next) {
      setPage(next);
    }
  }, []);

  function navigatePage(next: PageName) {
    setPage(next);
    const url = new URL(window.location.href);
    if (next === "Command") {
      url.searchParams.delete("page");
    } else {
      url.searchParams.set("page", next);
    }
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  const filteredMessages = useMemo(
    () => filterMessages(data.messages, filters),
    [data.messages, filters],
  );
  const filteredEntities = useMemo(
    () => filterEntities(data.entities, filteredMessages, filters),
    [data.entities, filteredMessages, filters],
  );
  const chatSummaries = useMemo(
    () => filterChatSummaries(data.chatSummaries, filteredMessages, filters),
    [data.chatSummaries, filteredMessages, filters],
  );
  const chatTypes = useMemo(
    () => ["All", ...new Set(data.chatSummaries.map((row) => row.chat_type))],
    [data.chatSummaries],
  );
  const bounds = useMemo(() => timestampBounds(data.messages), [data.messages]);
  const collection = useMemo(() => collectionBreakdown(payload.chats), [payload.chats]);
  const risk = useMemo(() => riskSummary(payload), [payload]);
  const caseCount = useMemo(
    () => buildPersonnelFromPayload(payload).map(enrichPersonnelRisk).length,
    [payload],
  );

  const intelEarliest = bounds.min || "—";
  const intelLatest = bounds.max || "—";
  const highCritical = (risk.levels.High || 0) + (risk.levels.Critical || 0);

  function toggleChat(chatId: number) {
    setFilters((prev) => {
      const has = prev.chatIds.includes(chatId);
      return {
        ...prev,
        chatIds: has ? prev.chatIds.filter((id) => id !== chatId) : [...prev.chatIds, chatId],
      };
    });
  }

  const pages: Record<PageName, () => ReactNode> = {
    Command: () => (
      <CommandPage
        payload={payload}
        filteredMessages={filteredMessages}
        chatSummaries={chatSummaries}
        onNavigate={navigatePage}
      />
    ),
    Cases: () => <CasesPage payload={payload} />,
    Intel: () => <IntelPage messages={filteredMessages} entities={filteredEntities} />,
    Sources: () => <SourcesPage chatSummaries={chatSummaries} messages={filteredMessages} />,
    Analytics: () => (
      <AnalyticsPage
        payload={payload}
        filteredMessages={filteredMessages}
        filteredEntities={filteredEntities}
      />
    ),
    Ops: () => (
      <OpsPage
        payload={payload}
        filteredMessages={filteredMessages}
        filteredEntities={filteredEntities}
      />
    ),
    ThreatSimulation: () => <ThreatSimulationPage />,
  };

  return (
    <div className={`dashboard-layout${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <AppSidebar
        page={page}
        onNavigate={navigatePage}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
        settingsOpen={settingsOpen}
        onToggleSettings={() => setSettingsOpen((v) => !v)}
        autoRefresh={autoRefresh}
        lastFetchedAt={lastFetchedAt}
        filters={filters}
        setFilters={setFilters}
        chatTypes={chatTypes}
        chatSummaries={data.chatSummaries}
        bounds={bounds}
        refreshSeconds={refreshSeconds}
        onAutoRefreshChange={onAutoRefreshChange}
        onRefreshSecondsChange={onRefreshSecondsChange}
        onManualRefresh={onManualRefresh}
        onToggleChat={toggleChat}
      />

      <main className="dashboard-main">
        <AppNavbar
          page={page}
          source={source}
          autoRefresh={autoRefresh}
          refreshSeconds={refreshSeconds}
          collection={collection}
          intelWindow={`${filteredMessages.length} flagged · ${intelEarliest} → ${intelLatest}`}
          riskPosture={`${highCritical} high+ · ${caseCount} cases`}
          onManualRefresh={onManualRefresh}
        />

        {isSim ? <SimulationBanner /> : null}

        {page === "Command" ? (
          <ScrapeControl onScrapeComplete={() => onManualRefresh?.()} />
        ) : null}

        {source === "sample" || source === "demo" || source === "empty" ? (
          <div className="notice">
            Showing sample / demo data. Run a scrape and keep the API online for live Mongo intel.
          </div>
        ) : null}

        {pages[page]()}
      </main>
    </div>
  );
}
