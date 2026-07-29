"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useDataMode } from "@/components/mode/DataModeProvider";
import { ScrapeControl } from "@/components/ScrapeControl";
import { SimulationSettingsPanel } from "@/components/simulation/SimulationSettingsPanel";
import {
  buildExportDashboard,
  defaultFilters,
  filterChatSummaries,
  filterMessages,
} from "@/lib/dashboard-data";
import type { ExportPayload, MessageDisplayRow } from "@/lib/types";

type SourceTab = "all" | "channels" | "groups" | "dms";

function typeBadge(chatType: string): SourceTab | "group" {
  const t = chatType.toLowerCase();
  if (t === "channel") return "channels";
  if (t === "private chat") return "dms";
  return "group";
}

function formatTs(value: string): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function MessageDetail({ row }: { row: MessageDisplayRow }) {
  return (
    <article className="message-card sim-message-card">
      <div className="message-meta">
        <code>{formatTs(row.timestamp)}</code>
        <span>{row.sender}</span>
        <span className={`risk-badge risk-${String(row.risk_level || "Low").toLowerCase()}`}>
          {row.risk_level}
        </span>
      </div>
      <p>{row.text || "(no text)"}</p>
      <div className="sim-message-meta-grid caption">
        <span>Msg ID: {row.message_id}</span>
        <span>Chat: {row.chat_id}</span>
        {row.media_type ? <span>Media: {row.media_type}</span> : null}
        {row.views !== "" && row.views != null ? <span>Views: {row.views}</span> : null}
        {row.reply_to_message_id ? <span>Reply to: {row.reply_to_message_id}</span> : null}
        {row.forward_from_chat_id ? (
          <span>
            Forward from: {row.forward_from_chat_id}
            {row.forward_from_message_id ? ` #${row.forward_from_message_id}` : ""}
          </span>
        ) : null}
        <span>Flags: {row.keywords || "—"}</span>
      </div>
    </article>
  );
}

export function ThreatSimulationPage() {
  const { mode, simulation } = useDataMode();
  const [payload, setPayload] = useState<ExportPayload | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<SourceTab>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await fetch("/api/data", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Failed to load simulation data");
      setPayload(body.payload as ExportPayload);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData, mode, simulation.simulation_active, simulation.session_id, simulation.scenario]);

  useEffect(() => {
    if (mode !== "simulation") return;
    const timer = window.setInterval(() => void loadData(), 4000);
    return () => window.clearInterval(timer);
  }, [mode, loadData]);

  const dashboard = useMemo(() => {
    if (!payload) return null;
    return buildExportDashboard(payload);
  }, [payload]);

  const filters = useMemo(
    () => defaultFilters((payload?.chats || []).map((c) => c.id)),
    [payload],
  );

  const chatSummaries = useMemo(() => {
    if (!dashboard) return [];
    let rows = filterChatSummaries(dashboard.chatSummaries, dashboard.messages, filters);
    if (tab === "channels") rows = rows.filter((c) => typeBadge(c.chat_type) === "channels");
    if (tab === "groups") rows = rows.filter((c) => typeBadge(c.chat_type) === "group");
    if (tab === "dms") rows = rows.filter((c) => typeBadge(c.chat_type) === "dms");
    return rows;
  }, [dashboard, tab, filters]);

  const messages = useMemo(() => {
    if (!dashboard) return [];
    return filterMessages(dashboard.messages, filters);
  }, [dashboard, filters]);

  useEffect(() => {
    if (chatSummaries.length && selectedId == null) {
      setSelectedId(chatSummaries[0]?.chat_id ?? null);
    }
  }, [chatSummaries, selectedId]);

  const selected = chatSummaries.find((c) => c.chat_id === selectedId) ?? null;
  const sourceMessages = useMemo(() => {
    if (selectedId == null) return [];
    return messages.filter((m) => m.chat_id === selectedId);
  }, [messages, selectedId]);

  const counts = useMemo(() => {
    if (!dashboard) return { channels: 0, groups: 0, dms: 0, messages: 0 };
    let channels = 0;
    let groups = 0;
    let dms = 0;
    for (const c of dashboard.chatSummaries) {
      const t = typeBadge(c.chat_type);
      if (t === "channels") channels += 1;
      else if (t === "dms") dms += 1;
      else groups += 1;
    }
    return { channels, groups, dms, messages: dashboard.messages.length };
  }, [dashboard]);

  if (mode !== "simulation") {
    return (
      <div className="standalone-main">
        <div className="page-header">
          <h1>Threat Simulator</h1>
          <p>Enable simulation mode from the header to generate and inspect synthetic Telegram data.</p>
        </div>
        <div className="empty-state">Switch to Simulation mode to use the threat simulator.</div>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>Threat Simulator</h1>
        <p>
          AI-generated criminal-intent messages with full scrape metadata — channels, groups, and private DMs.
        </p>
      </div>


      {error ? <div className="error compact">{error}</div> : null}

      <ScrapeControl
        generateLabel="▶ Generate"
        onScrapeComplete={() => void loadData()}
      />

      <section className="panel card simulation-settings-card">
        <SimulationSettingsPanel onScenarioApplied={() => void loadData()} />
      </section>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">Channels</div>
          <div className="metric-value">{counts.channels}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Groups</div>
          <div className="metric-value">{counts.groups}</div>
        </div>
        <div className="metric-card tone-accent">
          <div className="metric-label">Private DMs</div>
          <div className="metric-value">{counts.dms}</div>
        </div>
        <div className="metric-card tone-primary">
          <div className="metric-label">Flagged messages</div>
          <div className="metric-value">{counts.messages}</div>
        </div>
      </div>

      <div className="sim-tab-row">
        {(
          [
            ["all", "All sources"],
            ["channels", "Channels"],
            ["groups", "Groups"],
            ["dms", "DMs"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`btn ${tab === id ? "primary" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="personnel-layout">
        <section className="panel card">
          <h2>Generated sources ({chatSummaries.length})</h2>
          {!chatSummaries.length ? (
            <div className="empty-state">
              No generated data yet. Use <strong>▶ Run Dummy Scrape</strong> above to populate the
              simulation database.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Type</th>
                    <th>Volume</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {chatSummaries.map((chat) => (
                    <tr
                      key={chat.chat_id}
                      className={selectedId === chat.chat_id ? "personnel-row active" : "personnel-row"}
                      onClick={() => setSelectedId(chat.chat_id)}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedId(chat.chat_id);
                        }
                      }}
                    >
                      <td>
                        <strong>{chat.title}</strong>
                        <div className="caption mono">ID {chat.chat_id}</div>
                      </td>
                      <td>
                        <span className={`source-badge type-${typeBadge(chat.chat_type)}`}>
                          {chat.chat_type}
                        </span>
                      </td>
                      <td>{chat.messages}</td>
                      <td>
                        <span
                          className={`risk-badge risk-${String(chat.risk_level || "Low").toLowerCase()}`}
                        >
                          {chat.risk_level} · {chat.risk_score}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel card">
          {!selected ? (
            <div className="empty-state">Select a channel, group, or DM to inspect messages.</div>
          ) : (
            <>
              <div className="personnel-detail-head">
                <div>
                  <h2>{selected.title}</h2>
                  <p className="caption">
                    {selected.chat_type} · {selected.messages} flagged · narcotics {selected.narcotics} ·
                    trafficking {selected.human_trafficking} · firearms {selected.firearms}
                  </p>
                </div>
              </div>
              <div className="message-history">
                {!sourceMessages.length ? (
                  <div className="empty-state">No flagged messages for this source.</div>
                ) : (
                  sourceMessages.map((row) => (
                    <MessageDetail key={`${row.chat_id}-${row.message_id}`} row={row} />
                  ))
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
