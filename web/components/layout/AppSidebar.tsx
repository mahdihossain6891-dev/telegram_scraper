"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { SimulationSettingsPanel } from "@/components/simulation/SimulationSettingsPanel";
import { useDataMode } from "@/components/mode/DataModeProvider";
import { NAV_GROUPS, pageLabel, type PageName } from "@/lib/constants";
import { formatSimulationScenarioLabels } from "@/lib/simulation-settings";
import { KEYWORD_ENTITY_TYPES } from "@/lib/constants";
import type { ChatSummaryRow, DashboardFilters } from "@/lib/types";

export type AppSidebarProps = {
  page: PageName;
  onNavigate: (page: PageName) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  settingsOpen: boolean;
  onToggleSettings: () => void;
  autoRefresh: boolean;
  lastFetchedAt: string;
  filters: DashboardFilters;
  setFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  chatTypes: string[];
  chatSummaries: ChatSummaryRow[];
  bounds: { min: string; max: string };
  refreshSeconds: number;
  onAutoRefreshChange?: (enabled: boolean) => void;
  onRefreshSecondsChange?: (seconds: number) => void;
  onManualRefresh?: () => void;
  onToggleChat: (chatId: number) => void;
};

const NAV_ICONS: Record<PageName, string> = {
  Command: "◈",
  Intel: "◎",
  Ops: "⚡",
  Sources: "⬡",
  Cases: "◎",
  Analytics: "▤",
  ThreatIntelligence: "✧",
  ThreatSimulation: "⬡",
};

export function AppSidebar({
  page,
  onNavigate,
  collapsed,
  onToggleCollapse,
  settingsOpen,
  onToggleSettings,
  autoRefresh,
  lastFetchedAt,
  filters,
  setFilters,
  chatTypes,
  chatSummaries,
  bounds,
  refreshSeconds,
  onAutoRefreshChange,
  onRefreshSecondsChange,
  onManualRefresh,
  onToggleChat,
}: AppSidebarProps) {
  const { mode, simulation } = useDataMode();
  const isSim = mode === "simulation" && simulation.simulation_active;

  return (
    <aside className={`sidebar soc-sidebar${collapsed ? " collapsed" : ""}`} aria-label="Main navigation">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <span className="brand-icon" aria-hidden="true">
            TC
          </span>
          {!collapsed ? (
            <div>
              <h2>Threat Console</h2>
              <p>SOC · Telegram OSINT</p>
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <div className="sidebar-live">
        <span className={`live-dot ${autoRefresh ? "" : "paused"}`} aria-hidden="true" />
        {!collapsed ? (
          <div>
            <strong>{isSim ? "Simulation" : autoRefresh ? "Live" : "Paused"}</strong>
            <div className="caption">
              {isSim && simulation.scenario
                ? `Scenarios · ${formatSimulationScenarioLabels(simulation.scenario)}`
                : lastFetchedAt
                  ? `Updated ${lastFetchedAt}`
                  : "—"}
            </div>
          </div>
        ) : null}
      </div>

      <nav className="sidebar-nav" aria-label="Dashboard pages">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="nav-group">
            {!collapsed ? <div className="nav-group-label">{group.label}</div> : null}
            {group.pages.map((name) => (
              <button
                key={name}
                type="button"
                className={page === name ? "nav-btn active" : "nav-btn"}
                onClick={() => onNavigate(name)}
                aria-current={page === name ? "page" : undefined}
                title={pageLabel(name)}
              >
                <span className="nav-icon" aria-hidden="true">
                  {NAV_ICONS[name]}
                </span>
                {!collapsed ? <span className="nav-label">{pageLabel(name)}</span> : null}
              </button>
            ))}
          </div>
        ))}
        <div className="nav-group">
          {!collapsed ? <div className="nav-group-label">Intel+</div> : null}
          <a href="/behavioral-analytics" className="nav-btn ba-nav-link" title="Behavioral Analytics">
            <span className="nav-icon" aria-hidden="true">
              ◉
            </span>
            {!collapsed ? <span className="nav-label">Behavioral Analytics</span> : null}
          </a>
          <a href="/ai" className="nav-btn ba-nav-link ai-nav-link" title="Sébastien">
            <span className="nav-icon" aria-hidden="true">
              ✦
            </span>
            {!collapsed ? (
              <span className="nav-label-stack">
                <span className="ai-nav-title">Sébastien</span>
                <span className="ai-nav-sub">AI Copilot</span>
              </span>
            ) : null}
          </a>
        </div>
      </nav>

      <div className="sidebar-footer">
        <Link
          href="/settings"
          className="nav-btn settings-toggle"
          title="API keys & configuration"
        >
          <span className="nav-icon" aria-hidden="true">
            ⚙
          </span>
          {!collapsed ? <span className="nav-label">Settings</span> : null}
        </Link>
        <button
          type="button"
          className={`nav-btn scope-toggle${settingsOpen ? " active" : ""}`}
          onClick={onToggleSettings}
          aria-expanded={settingsOpen}
          title="Scope & refresh"
        >
          <span className="nav-icon" aria-hidden="true">
            ⊞
          </span>
          {!collapsed ? <span className="nav-label">Scope</span> : null}
        </button>
      </div>

      {settingsOpen ? (
        <div className="sidebar-settings" role="region" aria-label="Scope and refresh">
          {isSim ? <SimulationSettingsPanel /> : null}
          <ScopePanel
            filters={filters}
            setFilters={setFilters}
            chatTypes={chatTypes}
            chatSummaries={chatSummaries}
            bounds={bounds}
            onToggleChat={onToggleChat}
          />
          <div className="sidebar-section refresh-panel">
            <div className="nav-group-label">Live</div>
            <div className="refresh-row">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => onAutoRefreshChange?.(e.target.checked)}
                />
                <span>Auto-refresh</span>
              </label>
              <label className="inline-number">
                every
                <input
                  type="number"
                  min={10}
                  max={300}
                  aria-label="Refresh interval seconds"
                  value={refreshSeconds}
                  onChange={(e) => onRefreshSecondsChange?.(Number(e.target.value))}
                />
                s
              </label>
            </div>
            <button type="button" className="btn primary block" onClick={() => onManualRefresh?.()}>
              Refresh now
            </button>
          </div>
        </div>
      ) : null}
    </aside>
  );
}

function ScopePanel({
  filters,
  setFilters,
  chatTypes,
  chatSummaries,
  bounds,
  onToggleChat,
}: {
  filters: DashboardFilters;
  setFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  chatTypes: string[];
  chatSummaries: ChatSummaryRow[];
  bounds: { min: string; max: string };
  onToggleChat: (chatId: number) => void;
}): ReactNode {
  return (
    <div className="sidebar-section scope-panel">
      <div className="nav-group-label">Scope</div>

      <div className="field-block">
        <label className="check-row">
          <input
            type="checkbox"
            checked={filters.includePrivate}
            onChange={(e) => setFilters({ ...filters, includePrivate: e.target.checked })}
          />
          <span>Include private DMs</span>
        </label>
      </div>

      <div className="field-block">
        <span className="field-label">Chat type</span>
        <select
          value={filters.chatType}
          onChange={(e) => setFilters({ ...filters, chatType: e.target.value })}
          aria-label="Chat type"
        >
          {chatTypes.map((type) => (
            <option key={type}>{type}</option>
          ))}
        </select>
      </div>

      <div className="field-block">
        <span className="field-label">Categories</span>
        <div className="filter-chips" role="group" aria-label="Keyword categories">
          <button
            type="button"
            className={!filters.categories.length ? "filter-chip active" : "filter-chip"}
            aria-pressed={!filters.categories.length}
            onClick={() => setFilters((prev) => ({ ...prev, categories: [] }))}
          >
            All
          </button>
          {[...KEYWORD_ENTITY_TYPES].map((category) => {
            const active = filters.categories.includes(category);
            return (
              <button
                key={category}
                type="button"
                className={active ? "filter-chip active" : "filter-chip"}
                aria-pressed={active}
                onClick={() =>
                  setFilters((prev) => {
                    const next = active
                      ? prev.categories.filter((c) => c !== category)
                      : [...prev.categories, category];
                    return { ...prev, categories: next };
                  })
                }
              >
                {category.replace(/_/g, " ")}
              </button>
            );
          })}
        </div>
      </div>

      <div className="field-block">
        <div className="sources-head">
          <span className="field-label">Sources</span>
          <div className="field-actions">
            <button
              type="button"
              className="btn ghost"
              onClick={() =>
                setFilters((prev) => ({
                  ...prev,
                  chatIds: chatSummaries.map((c) => c.chat_id),
                }))
              }
            >
              Select all
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => setFilters((prev) => ({ ...prev, chatIds: [] }))}
            >
              Clear
            </button>
          </div>
        </div>
        <div className="chat-list compact">
          {chatSummaries.slice(0, 12).map((chat) => (
            <label key={chat.chat_id} className="check-row">
              <input
                type="checkbox"
                checked={filters.chatIds.includes(chat.chat_id)}
                onChange={() => onToggleChat(chat.chat_id)}
              />
              <span className="truncate">{chat.title}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="field-block">
        <label className="check-row">
          <input
            type="checkbox"
            checked={filters.useDateFilter}
            onChange={(e) => setFilters({ ...filters, useDateFilter: e.target.checked })}
          />
          <span>Date range</span>
        </label>
        {filters.useDateFilter ? (
          <div className="date-row">
            <label>
              From
              <input
                type="date"
                value={filters.dateFrom || bounds.min}
                onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
              />
            </label>
            <label>
              To
              <input
                type="date"
                value={filters.dateTo || bounds.max}
                onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
              />
            </label>
          </div>
        ) : null}
      </div>
    </div>
  );
}
