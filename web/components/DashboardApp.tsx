"use client";

import { useMemo, useState } from "react";

import { PlotChart } from "@/components/PlotChart";
import { KEYWORD_ENTITY_TYPES, LINK_ENTITY_TYPES, PAGE_NAMES, type PageName } from "@/lib/constants";
import {
  buildExportDashboard,
  categoryCountsFromMessages,
  chatTypeBreakdown,
  computeInsights,
  defaultFilters,
  filterChatSummaries,
  filterEntities,
  filterMessages,
  mediaTypeBreakdown,
  messagesPerHour,
  multiCategoryMessages,
  senderActivity,
  timelineFromMessages,
  timestampBounds,
  topEntitiesByType,
  topKeywordTerms,
  wordFrequency,
} from "@/lib/dashboard-data";
import { downloadText, rowsToCsv } from "@/lib/csv";
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

function Metric({
  label,
  value,
  delta,
  tone = "primary",
}: {
  label: string;
  value: string | number;
  delta?: string | number;
  tone?: "primary" | "accent" | "danger";
}) {
  return (
    <div className={`metric-card tone-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {delta !== undefined ? <div className="metric-delta">{delta}</div> : null}
    </div>
  );
}

function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
    </div>
  );
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) {
    return <div className="empty-state">No rows match the current filters.</div>;
  }
  const headers = Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => (
                <td key={header}>{String(row[header] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
  const data = useMemo(() => buildExportDashboard(payload), [payload]);
  const allChatIds = useMemo(() => data.chatSummaries.map((row) => row.chat_id), [data.chatSummaries]);
  const [page, setPage] = useState<PageName>("Overview");
  const [filters, setFilters] = useState<DashboardFilters>(() => defaultFilters(allChatIds));
  const [selectedChatId, setSelectedChatId] = useState<number | null>(data.chatSummaries[0]?.chat_id ?? null);
  const [messageLimit, setMessageLimit] = useState(200);
  const [messageSort, setMessageSort] = useState("Newest first");
  const [entityLimit, setEntityLimit] = useState(500);
  const [entityType, setEntityType] = useState("All");
  const [entityView, setEntityView] = useState("All entities");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchLimit, setSearchLimit] = useState(100);

  const filteredMessages = useMemo(() => filterMessages(data.messages, filters), [data.messages, filters]);
  const chatSummaries = useMemo(
    () => filterChatSummaries(data.chatSummaries, filteredMessages, filters),
    [data.chatSummaries, filteredMessages, filters],
  );
  const filteredEntities = useMemo(
    () => filterEntities(data.entities, filteredMessages, filters),
    [data.entities, filteredMessages, filters],
  );
  const categoryCounts = useMemo(
    () => categoryCountsFromMessages(filteredMessages),
    [filteredMessages],
  );
  const termRows = useMemo(() => topKeywordTerms(filteredEntities, 20), [filteredEntities]);
  const insights = useMemo(
    () => computeInsights(chatSummaries, filteredMessages, categoryCounts, termRows),
    [chatSummaries, filteredMessages, categoryCounts, termRows],
  );
  const timeline = useMemo(() => timelineFromMessages(filteredMessages), [filteredMessages]);
  const chatTypes = useMemo(
    () => ["All", ...new Set(data.chatSummaries.map((row) => row.chat_type))],
    [data.chatSummaries],
  );
  const maxMessagesPerChat = useMemo(
    () => Math.max(...data.chatSummaries.map((row) => row.messages), 0),
    [data.chatSummaries],
  );

  const sortedMessages = useMemo(() => {
    const rows = [...filteredMessages];
    if (messageSort === "Oldest first") {
      rows.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    } else if (messageSort === "Chat name") {
      rows.sort((a, b) => a.chat.localeCompare(b.chat) || a.timestamp.localeCompare(b.timestamp));
    } else if (messageSort === "Most entities") {
      rows.sort((a, b) => b.entities - a.entities);
    }
    return rows.slice(0, messageLimit);
  }, [filteredMessages, messageLimit, messageSort]);

  const chatMessages = useMemo(() => {
    if (!selectedChatId) {
      return [];
    }
    return sortedMessages.filter((row) => row.chat_id === selectedChatId).slice(0, 200);
  }, [selectedChatId, sortedMessages]);

  const searchResults = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    if (!needle) {
      return [];
    }
    return filteredMessages
      .filter((row) => row.text.toLowerCase().includes(needle))
      .slice(0, searchLimit);
  }, [filteredMessages, searchQuery, searchLimit]);

  const entityRows = useMemo(() => {
    let rows = filteredEntities.slice(0, entityLimit);
    if (entityType !== "All") {
      rows = rows.filter((row) => row.entity_type === entityType);
    }
    if (entityView === "Links & contacts") {
      rows = rows.filter((row) => LINK_ENTITY_TYPES.has(row.entity_type));
    } else if (entityView === "Keyword flags only") {
      rows = rows.filter((row) => KEYWORD_ENTITY_TYPES.has(row.entity_type));
    }
    return rows;
  }, [filteredEntities, entityLimit, entityType, entityView]);

  const bounds = useMemo(() => timestampBounds(data.messages), [data.messages]);

  function toggleChat(chatId: number) {
    setFilters((current) => {
      const selected = new Set(current.chatIds);
      if (selected.has(chatId)) {
        selected.delete(chatId);
      } else {
        selected.add(chatId);
      }
      return { ...current, chatIds: [...selected] };
    });
  }

  function renderOverview() {
    return (
      <>
        <PageHeader
          title="Overview"
          subtitle="Flagged Telegram activity across monitored chats — dense ops view for keyword hits."
        />
        <div className="metric-grid">
          <Metric label="Flagged messages" value={filteredMessages.length} tone="accent" />
          <Metric label="Flagged chats" value={chatSummaries.length} />
          <Metric label="Keyword flags" value={termRows.reduce((sum, row) => sum + row.count, 0)} />
          <Metric label="Filtered chats" value={chatSummaries.length} />
        </div>
        <div className="metric-grid">
          <Metric label="Busiest chat" value={insights.busiestChat || "—"} />
          <Metric label="Top keyword" value={insights.topKeyword || "—"} delta={insights.topKeywordCount} tone="accent" />
          <Metric label="Top category" value={insights.topCategory || "—"} delta={insights.topCategoryCount} />
          <Metric label="Multi-flag msgs" value={insights.multiFlagMessages} tone="danger" />
        </div>
        {insights.earliestMessage ? (
          <p className="caption">
            Filtered activity window: {insights.earliestMessage} → {insights.latestMessage} ·{" "}
            {insights.privateSharePct}% of flagged messages are from private chats
          </p>
        ) : null}
        <div className="two-col">
          <section className="panel card">
            <h2>All flagged chats</h2>
            <DataTable rows={chatSummaries as unknown as Record<string, unknown>[]} />
            {chatSummaries.length ? (
              <PlotChart
                data={[{ type: "bar", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.messages) }]}
                layout={{ title: "Flagged Messages Per Chat" }}
              />
            ) : null}
          </section>
          <section className="panel card">
            <h2>Keyword categories</h2>
            <DataTable rows={categoryCounts as unknown as Record<string, unknown>[]} />
            {categoryCounts.length ? (
              <PlotChart
                data={[{ type: "bar", x: categoryCounts.map((row) => row.category), y: categoryCounts.map((row) => row.count) }]}
                layout={{ title: "Keyword Flags By Category" }}
              />
            ) : null}
            <h2>Top keyword terms</h2>
            <DataTable rows={termRows.slice(0, 10) as unknown as Record<string, unknown>[]} />
          </section>
        </div>
        {timeline.length ? (
          <section className="panel card">
            <PlotChart
              data={[{ type: "scatter", mode: "lines+markers", x: timeline.map((row) => row.date), y: timeline.map((row) => row.messages) }]}
              layout={{ title: "Flagged Messages Over Time", xaxis: { title: "Date" }, yaxis: { title: "Messages" } }}
            />
          </section>
        ) : null}
        <div className="two-col">
          <section className="panel card">
            <PlotChart
              data={[{
                type: "pie",
                labels: chatTypeBreakdown(chatSummaries).map((row) => row.chat_type),
                values: chatTypeBreakdown(chatSummaries).map((row) => row.messages),
                hole: 0.35,
              }]}
              layout={{ title: "Messages by Chat Type" }}
            />
          </section>
          <section className="panel card">
            <PlotChart
              data={[
                { type: "bar", name: "Narcotics", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.narcotics), marker: { color: "#ef4444" } },
                { type: "bar", name: "Trafficking", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.human_trafficking), marker: { color: "#f97316" } },
                { type: "bar", name: "Firearms", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.firearms), marker: { color: "#3b82f6" } },
              ]}
              layout={{ barmode: "stack", title: "Keyword Categories by Chat" }}
            />
          </section>
        </div>
        <section className="panel card">
          <h2>Recent flagged messages</h2>
          <DataTable rows={filteredMessages.slice(0, 25) as unknown as Record<string, unknown>[]} />
        </section>
      </>
    );
  }

  function renderChats() {
    return (
      <>
        <PageHeader title="Chats" subtitle="Per-chat flagged volume and category mix." />
        <p className="caption">Detailed breakdown for every flagged chat in the export.</p>
        <section className="panel card">
          <DataTable rows={chatSummaries as unknown as Record<string, unknown>[]} />
          <button type="button" className="btn" onClick={() => downloadText("chat_summary.csv", rowsToCsv(chatSummaries as unknown as Record<string, unknown>[]), "text/csv")}>
            Download chat summary CSV
          </button>
        </section>
        <section className="panel card">
          <label htmlFor="inspect-chat">Inspect chat</label>
          <select id="inspect-chat" value={selectedChatId ?? ""} onChange={(event) => setSelectedChatId(Number(event.target.value))}>
            {chatSummaries.map((row) => (
              <option key={row.chat_id} value={row.chat_id}>{row.title}</option>
            ))}
          </select>
          <h2>Messages in selected chat</h2>
          <DataTable rows={chatMessages as unknown as Record<string, unknown>[]} />
        </section>
      </>
    );
  }

  function renderMessages() {
    return (
      <>
        <PageHeader title="Messages" subtitle="Keyword-flagged message feed with sort and limit controls." />
        <div className="controls-row">
          <label>
            Max messages
            <input type="number" min={10} max={2000} step={50} value={messageLimit} onChange={(e) => setMessageLimit(Number(e.target.value))} />
          </label>
          <label>
            Sort by
            <select value={messageSort} onChange={(e) => setMessageSort(e.target.value)}>
              <option>Newest first</option>
              <option>Oldest first</option>
              <option>Chat name</option>
              <option>Most entities</option>
            </select>
          </label>
        </div>
        <p className="caption">Showing {sortedMessages.length} message(s)</p>
        <section className="panel card">
          <button type="button" className="btn" onClick={() => downloadText("filtered_messages.csv", rowsToCsv(sortedMessages as unknown as Record<string, unknown>[]), "text/csv")}>
            Download messages CSV
          </button>
          <DataTable rows={sortedMessages as unknown as Record<string, unknown>[]} />
          <details className="expander">
            <summary>Expanded message view</summary>
            {sortedMessages.slice(0, 50).map((row) => (
              <div key={`${row.chat_id}-${row.message_id}`} className="message-card">
                <strong>{row.chat}</strong> · <code>{row.timestamp}</code> · flags: {row.keywords}
                <p>{row.text || "(no text)"}</p>
              </div>
            ))}
          </details>
        </section>
      </>
    );
  }

  function renderKeywords() {
    const multiRows = multiCategoryMessages(filteredMessages, 50);
    return (
      <>
        <PageHeader title="Keywords" subtitle="Category breakdown and top matching terms." />
        <p className="caption">Keyword term frequency, category mix, and multi-category hits.</p>
        <div className="two-col">
          <section className="panel card">
            <PlotChart data={[{ type: "bar", x: categoryCounts.map((row) => row.category), y: categoryCounts.map((row) => row.count) }]} layout={{ title: "Keyword Flags By Category" }} />
          </section>
          <section className="panel card">
            <PlotChart
              data={[
                { type: "bar", name: "Narcotics", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.narcotics), marker: { color: "#ef4444" } },
                { type: "bar", name: "Trafficking", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.human_trafficking), marker: { color: "#f97316" } },
                { type: "bar", name: "Firearms", x: chatSummaries.map((row) => row.title), y: chatSummaries.map((row) => row.firearms), marker: { color: "#3b82f6" } },
              ]}
              layout={{ barmode: "stack", title: "Keyword Categories by Chat" }}
            />
          </section>
        </div>
        <section className="panel card">
          <PlotChart
            data={[{ type: "bar", orientation: "h", y: termRows.map((row) => `${row.term} (${row.category})`), x: termRows.map((row) => row.count) }]}
            layout={{ title: "Top Keyword Terms", height: Math.max(320, termRows.length * 28) }}
          />
          <DataTable rows={termRows as unknown as Record<string, unknown>[]} />
        </section>
        <section className="panel card">
          <h2>Multi-category messages</h2>
          <DataTable rows={multiRows as unknown as Record<string, unknown>[]} />
        </section>
      </>
    );
  }

  function renderAnalytics() {
    const hourly = messagesPerHour(filteredMessages);
    return (
      <>
        <PageHeader title="Analytics" subtitle="Timeline, hour-of-day, and chat-type distributions." />
        {timeline.length ? (
          <section className="panel card">
            <PlotChart data={[{ type: "scatter", mode: "lines+markers", x: timeline.map((row) => row.date), y: timeline.map((row) => row.messages) }]} layout={{ title: "Flagged Messages Over Time" }} />
          </section>
        ) : null}
        {hourly.length ? (
          <section className="panel card">
            <PlotChart data={[{ type: "bar", x: hourly.map((row) => row.hour), y: hourly.map((row) => row.messages) }]} layout={{ title: "Messages Per Hour" }} />
          </section>
        ) : null}
        <div className="two-col">
          <section className="panel card">
            <h2>Top senders (filtered)</h2>
            <DataTable rows={senderActivity(filteredMessages) as unknown as Record<string, unknown>[]} />
            <h2>Top domains</h2>
            <DataTable rows={topEntitiesByType(filteredEntities, "domain") as unknown as Record<string, unknown>[]} />
          </section>
          <section className="panel card">
            <h2>Top hashtags</h2>
            <DataTable rows={topEntitiesByType(filteredEntities, "hashtag") as unknown as Record<string, unknown>[]} />
            <h2>Top words</h2>
            <DataTable rows={wordFrequency(filteredMessages) as unknown as Record<string, unknown>[]} />
          </section>
        </div>
        <section className="panel card">
          <h2>Media types</h2>
          <DataTable rows={mediaTypeBreakdown(filteredMessages) as unknown as Record<string, unknown>[]} />
        </section>
      </>
    );
  }

  function renderEntities() {
    return (
      <>
        <PageHeader title="Entities" subtitle="Extracted links, handles, and keyword entities." />
        <div className="controls-row">
          <label>
            Max entities
            <input type="number" min={50} max={2000} step={50} value={entityLimit} onChange={(e) => setEntityLimit(Number(e.target.value))} />
          </label>
          <label>
            Entity type
            <select value={entityType} onChange={(e) => setEntityType(e.target.value)}>
              <option>All</option>
              {data.entityTypes.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="radio-row">
          {["All entities", "Links & contacts", "Keyword flags only"].map((option) => (
            <label key={option}>
              <input type="radio" name="entity-view" checked={entityView === option} onChange={() => setEntityView(option)} />
              {option}
            </label>
          ))}
        </div>
        <p className="caption">Showing {entityRows.length} entity row(s)</p>
        <section className="panel card">
          <button type="button" className="btn" onClick={() => downloadText("filtered_entities.csv", rowsToCsv(entityRows as unknown as Record<string, unknown>[]), "text/csv")}>
            Download entities CSV
          </button>
          <DataTable rows={entityRows as unknown as Record<string, unknown>[]} />
        </section>
      </>
    );
  }

  function renderSearch() {
    return (
      <>
        <PageHeader title="Search" subtitle="Full-text scan across filtered flagged messages." />
        <div className="controls-row">
          <label>
            Search message text
            <input type="search" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Enter a keyword or phrase" />
          </label>
          <label>
            Max results
            <input type="number" min={1} max={500} step={10} value={searchLimit} onChange={(e) => setSearchLimit(Number(e.target.value))} />
          </label>
        </div>
        {!searchQuery.trim() ? <p className="caption">Enter a keyword or phrase to search stored messages.</p> : null}
        {searchQuery.trim() ? (
          <section className="panel card">
            <p className="caption">{searchResults.length} result(s)</p>
            <button type="button" className="btn" onClick={() => downloadText("search_results.csv", rowsToCsv(searchResults as unknown as Record<string, unknown>[]), "text/csv")}>
              Download search results CSV
            </button>
            <DataTable rows={searchResults as unknown as Record<string, unknown>[]} />
          </section>
        ) : null}
      </>
    );
  }

  function renderExport() {
    return (
      <>
        <PageHeader title="Export" subtitle="Download the current export payload or filtered CSVs." />
        <p className="caption">Download the currently loaded export data from the browser.</p>
        <section className="panel card">
          <div className="button-row">
            <button type="button" className="btn primary" onClick={() => downloadText("export.json", JSON.stringify(payload, null, 2), "application/json")}>
              Download export.json
            </button>
            <button type="button" className="btn" onClick={() => downloadText("messages.csv", rowsToCsv(filteredMessages as unknown as Record<string, unknown>[]), "text/csv")}>
              Download filtered messages CSV
            </button>
            <button type="button" className="btn" onClick={() => downloadText("entities.csv", rowsToCsv(filteredEntities as unknown as Record<string, unknown>[]), "text/csv")}>
              Download filtered entities CSV
            </button>
          </div>
          <p className="caption">To refresh live data: run <code>export.bat</code> and <code>vercel_export.bat</code> locally, then push to GitHub.</p>
        </section>
      </>
    );
  }

  const pages: Record<PageName, () => React.ReactNode> = {
    Overview: renderOverview,
    Chats: renderChats,
    Messages: renderMessages,
    Keywords: renderKeywords,
    Analytics: renderAnalytics,
    Entities: renderEntities,
    Search: renderSearch,
    Export: renderExport,
  };

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">
            <span className={autoRefresh ? "live-dot" : "live-dot paused"} aria-hidden="true" />
            <h2>Telegram Scraper</h2>
          </div>
          <p>OSINT · keyword intelligence</p>
          <span className="version-badge">Dashboard v3 · dense</span>
        </div>
        <div className="sidebar-section">
          <h3>Live updates</h3>
          <label className="check-row">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(event) => onAutoRefreshChange?.(event.target.checked)}
            />
            Auto-refresh dashboard
          </label>
          <label>
            Refresh interval (seconds)
            <input
              type="number"
              min={15}
              max={600}
              step={15}
              value={refreshSeconds}
              onChange={(event) => onRefreshSecondsChange?.(Number(event.target.value))}
            />
          </label>
          <button type="button" className="btn primary" onClick={() => onManualRefresh?.()}>
            Refresh now
          </button>
          {lastFetchedAt ? <p className="sidebar-note">Last fetched: {lastFetchedAt}</p> : null}
        </div>
        <nav className="sidebar-nav" aria-label="Dashboard pages">
          {PAGE_NAMES.map((name) => (
            <button
              key={name}
              type="button"
              className={page === name ? "nav-btn active" : "nav-btn"}
              onClick={() => setPage(name)}
              aria-current={page === name ? "page" : undefined}
            >
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-section">
          <h3>Filters</h3>
          <label className="check-row">
            <input
              type="checkbox"
              checked={filters.includePrivate}
              onChange={(e) => setFilters({ ...filters, includePrivate: e.target.checked })}
            />
            Include private chats
          </label>
          <div className="chat-list">
            {data.chatSummaries.map((chat) => (
              <label key={chat.chat_id} className="check-row">
                <input
                  type="checkbox"
                  checked={filters.chatIds.includes(chat.chat_id)}
                  onChange={() => toggleChat(chat.chat_id)}
                />
                {chat.title} ({chat.messages} msgs)
              </label>
            ))}
          </div>
          <label>
            Keyword categories
            <select
              multiple
              value={filters.categories}
              onChange={(e) =>
                setFilters({
                  ...filters,
                  categories: [...e.target.selectedOptions].map((option) => option.value),
                })
              }
            >
              {[...KEYWORD_ENTITY_TYPES].map((category) => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </label>
          <label>
            Chat type
            <select value={filters.chatType} onChange={(e) => setFilters({ ...filters, chatType: e.target.value })}>
              {chatTypes.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </label>
          <label>
            Minimum messages per chat: {filters.minMessages}
            <input
              type="range"
              min={0}
              max={maxMessagesPerChat}
              value={filters.minMessages}
              onChange={(e) => setFilters({ ...filters, minMessages: Number(e.target.value) })}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={filters.useDateFilter}
              onChange={(e) => setFilters({ ...filters, useDateFilter: e.target.checked })}
            />
            Filter by date range
          </label>
          {filters.useDateFilter ? (
            <>
              <label>
                From
                <input type="date" value={filters.dateFrom || bounds.min} onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })} />
              </label>
              <label>
                To
                <input type="date" value={filters.dateTo || bounds.max} onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })} />
              </label>
            </>
          ) : null}
        </div>
        <div className="sidebar-section">
          <h3>Collection</h3>
          <p className="sidebar-note">
            Each Telegram DM is a separate chat. Scrape locally with <code>scrape_all.bat</code>, export, then redeploy.
          </p>
        </div>
      </aside>
      <main className="dashboard-main">
        {source === "sample" ? (
          <div className="notice" role="status">
            Showing sample data. Export locally with <code>export.bat</code>, copy to{" "}
            <code>web/public/data/export.json</code>, then redeploy on Vercel.
          </div>
        ) : null}
        <div className="status-bar" role="status">
          <span className={autoRefresh ? "status-pill live" : "status-pill idle"}>
            <span className={autoRefresh ? "live-dot" : "live-dot paused"} aria-hidden="true" />
            {autoRefresh ? `LIVE · ${refreshSeconds}s` : "IDLE"}
          </span>
          <span>
            Source: <strong>{source}</strong>
          </span>
          <span>
            Exported: <strong>{new Date(data.exportedAt).toLocaleString()}</strong>
          </span>
          {lastFetchedAt ? (
            <span>
              Fetched: <strong>{lastFetchedAt}</strong>
            </span>
          ) : null}
          <span>
            Flagged: <strong>{filteredMessages.length}</strong>
          </span>
        </div>
        {pages[page]()}
      </main>
    </div>
  );
}
