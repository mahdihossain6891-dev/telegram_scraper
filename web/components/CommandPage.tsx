"use client";

import { useMemo } from "react";

import {
  ActivityTable,
  ChannelCard,
  StatCard,
  ThreatChart,
  UserActivityCard,
} from "@/components/ui";
import {
  areaTimelineOption,
  categoryBarOption,
  donutSeverityOption,
  heatmapOption,
  peakActivityHeatmap,
} from "@/lib/charts";
import {
  categoryCountsFromMessages,
  timelineFromMessages,
} from "@/lib/dashboard-data";
import { buildPersonnelFromPayload, filterAndSortPersonnel } from "@/lib/personnel";
import { enrichPersonnelRisk, riskSummary } from "@/lib/risk";
import type { ChatSummaryRow, ExportPayload, MessageDisplayRow, PageNavigate } from "./page-types";

export type CommandPageProps = {
  payload: ExportPayload;
  filteredMessages: MessageDisplayRow[];
  chatSummaries?: ChatSummaryRow[];
  onNavigate: PageNavigate;
};

export function CommandPage({
  payload,
  filteredMessages,
  chatSummaries = [],
  onNavigate,
}: CommandPageProps) {
  const summary = useMemo(() => riskSummary(payload), [payload]);
  const timeline = useMemo(() => timelineFromMessages(filteredMessages), [filteredMessages]);
  const heatmap = useMemo(() => peakActivityHeatmap(filteredMessages), [filteredMessages]);
  const categoryCounts = useMemo(
    () => categoryCountsFromMessages(filteredMessages),
    [filteredMessages],
  );
  const topCases = useMemo(
    () =>
      filterAndSortPersonnel(buildPersonnelFromPayload(payload).map(enrichPersonnelRisk), {
        chatId: null,
        suspiciousOnly: true,
        keyword: "",
        query: "",
        dateFrom: "",
        dateTo: "",
        useDateFilter: false,
        sortBy: "suspicious_count",
      }).slice(0, 8),
    [payload],
  );

  const suspiciousChannels = useMemo(() => {
    return [...chatSummaries]
      .map((c) => ({
        ...c,
        flagged: filteredMessages.filter((m) => m.chat_id === c.chat_id).length,
      }))
      .sort((a, b) => b.flagged - a.flagged)
      .slice(0, 6);
  }, [chatSummaries, filteredMessages]);

  const threatEvents = useMemo(
    () =>
      filteredMessages
        .slice()
        .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
        .slice(0, 8),
    [filteredMessages],
  );

  const highCritical = (summary.levels.High || 0) + (summary.levels.Critical || 0);
  const activeChannels = chatSummaries.length || payload.chats?.length || 0;
  const riskScore = useMemo(() => {
    const total =
      (summary.levels.Low || 0) +
      (summary.levels.Medium || 0) +
      (summary.levels.High || 0) +
      (summary.levels.Critical || 0);
    if (!total) return 0;
    const weighted =
      (summary.levels.Low || 0) * 10 +
      (summary.levels.Medium || 0) * 40 +
      (summary.levels.High || 0) * 70 +
      (summary.levels.Critical || 0) * 95;
    return Math.round(weighted / total);
  }, [summary.levels]);

  return (
    <div className="soc-dashboard">
      <div className="page-header soc-page-header">
        <div>
          <p className="eyebrow">Threat overview</p>
          <p>Live threat posture across monitored Telegram collection sources.</p>
        </div>
      </div>

      <div className="metric-grid">
        <StatCard
          label="Flagged intel"
          value={filteredMessages.length}
          delta="In current scope"
          tone="primary"
        />
        <StatCard
          label="Critical / High"
          value={highCritical}
          delta="Messages by risk band"
          tone="danger"
        />
        <StatCard
          label="Active channels"
          value={activeChannels}
          delta={
            <button type="button" className="linkish" onClick={() => onNavigate("Sources")}>
              View channels
            </button>
          }
          tone="accent"
        />
        <StatCard
          label="Risk score"
          value={riskScore}
          delta={`${topCases.length} priority users`}
          tone="warning"
        />
      </div>

      <div className="two-col soc-analytics-row">
        <section className="panel card">
          <div className="panel-head">
            <h2>Activity pulse</h2>
            <span className="caption">Flagged volume over time</span>
          </div>
          {timeline.length ? (
            <ThreatChart
              option={areaTimelineOption(timeline)}
              height={280}
              ariaLabel="Flagged messages over time"
            />
          ) : (
            <div className="empty-state">No timeline data in scope.</div>
          )}
        </section>
        <section className="panel card">
          <div className="panel-head">
            <h2>Severity mix</h2>
            <span className="caption">Risk band distribution</span>
          </div>
          <ThreatChart
            option={donutSeverityOption(summary.levels)}
            height={280}
            ariaLabel="Severity distribution"
          />
        </section>
      </div>

      <div className="two-col">
        <section className="panel card">
          <div className="panel-head">
            <h2>Peak hours</h2>
            <span className="caption">Day × hour intensity</span>
          </div>
          <ThreatChart
            option={heatmapOption(heatmap)}
            height={280}
            ariaLabel="Peak activity heatmap"
          />
        </section>
        <section className="panel card">
          <div className="panel-head">
            <h2>Category mix</h2>
            <span className="caption">Keyword flags</span>
          </div>
          {categoryCounts.length ? (
            <ThreatChart
              option={categoryBarOption(categoryCounts)}
              height={280}
              ariaLabel="Category breakdown"
            />
          ) : (
            <div className="empty-state">No category hits in scope.</div>
          )}
        </section>
      </div>

      <div className="soc-tables-row">
        <section className="panel card">
          <div className="panel-head">
            <h2>Flagged users</h2>
            <button type="button" className="btn" onClick={() => onNavigate("Cases")}>
              Investigate
            </button>
          </div>
          {!topCases.length ? (
            <div className="empty-state">No suspects with flagged activity yet.</div>
          ) : (
            <div className="user-card-list">
              {topCases.slice(0, 5).map((row) => (
                <UserActivityCard
                  key={row.user_id}
                  name={row.display_name}
                  userId={row.user_id}
                  riskLevel={String(row.risk_level || "Low")}
                  riskScore={row.risk_score ?? 0}
                  flagged={row.suspicious_count}
                  source={row.group_name || "—"}
                />
              ))}
            </div>
          )}
        </section>

        <section className="panel card">
          <div className="panel-head">
            <h2>Suspicious channels</h2>
            <button type="button" className="btn" onClick={() => onNavigate("Sources")}>
              All channels
            </button>
          </div>
          {!suspiciousChannels.length ? (
            <div className="empty-state">No channels in scope.</div>
          ) : (
            <div className="channel-card-list">
              {suspiciousChannels.map((ch) => (
                <ChannelCard
                  key={ch.chat_id}
                  title={ch.title}
                  type={ch.chat_type}
                  messageCount={ch.messages}
                  flaggedCount={ch.flagged}
                  riskHint={ch.risk_level}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="panel card">
        <div className="panel-head">
          <h2>Threat events</h2>
          <button type="button" className="btn" onClick={() => onNavigate("Intel")}>
            Threat monitoring
          </button>
        </div>
        <ActivityTable
          columns={[
            { key: "when", header: "When" },
            { key: "source", header: "Source" },
            { key: "text", header: "Signal" },
            { key: "severity", header: "Severity" },
          ]}
          rows={threatEvents as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => String(row.message_id ?? row.timestamp)}
          emptyMessage="No flagged events in scope."
          renderCell={(row, key) => {
            const msg = row as unknown as MessageDisplayRow;
            if (key === "when") {
              return <span className="caption mono">{String(msg.timestamp || "—").slice(0, 16)}</span>;
            }
            if (key === "source") {
              return <span className="truncate">{msg.chat || "—"}</span>;
            }
            if (key === "text") {
              return (
                <span className="truncate">
                  {(msg.text || msg.keywords || "—").toString().slice(0, 80)}
                </span>
              );
            }
            if (key === "severity") {
              const sev = String(msg.risk_level || "Medium");
              return <span className={`risk-badge risk-${sev.toLowerCase()}`}>{sev}</span>;
            }
            return null;
          }}
        />
      </section>
    </div>
  );
}
