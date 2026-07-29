"use client";

import { useEffect, useMemo, useState } from "react";

import type { ThreatReport } from "@/components/ai/threat-report";
import type { AiRetrieved } from "@/components/ai/types";
import { riskBandClass } from "@/lib/risk-bands";

type Tab = "events" | "messages" | "relationships";

type Focus = "risk" | "behavior" | "alerts" | "network" | "report" | "general";

type Props = {
  report: ThreatReport | null;
  retrieved?: AiRetrieved[];
  workflow?: Record<string, unknown>;
  focus?: Focus;
};

type TimelineRow = {
  id: string;
  kind: Tab;
  timestamp: string;
  title: string;
  detail: string;
  band?: string;
};

function defaultTabForFocus(focus: Focus): Tab {
  if (focus === "network") return "relationships";
  if (focus === "behavior" || focus === "alerts") return "messages";
  return "messages";
}

function tabsForFocus(focus: Focus): Array<[Tab, string]> {
  if (focus === "network") {
    return [
      ["relationships", "Relationships"],
      ["messages", "Messages"],
      ["events", "Events"],
    ];
  }
  if (focus === "behavior" || focus === "alerts") {
    return [
      ["messages", "Messages"],
      ["events", "Events"],
      ["relationships", "Relationships"],
    ];
  }
  return [
    ["messages", "Messages"],
    ["relationships", "Relationships"],
    ["events", "Events"],
  ];
}

export function InvestigationTimeline({
  report,
  retrieved,
  workflow,
  focus = "general",
}: Props) {
  const [tab, setTab] = useState<Tab>(() => defaultTabForFocus(focus));
  const tabOptions = tabsForFocus(focus);

  useEffect(() => {
    setTab(defaultTabForFocus(focus));
  }, [focus]);

  const rows = useMemo(() => {
    const out: TimelineRow[] = [];

    const tools = (workflow?.tools_executed as Array<Record<string, unknown>>) || [];
    for (const [i, tool] of tools.entries()) {
      out.push({
        id: `event-${i}`,
        kind: "events",
        timestamp: tool.latency_ms != null ? `${tool.latency_ms}ms` : "—",
        title: String(tool.tool || tool.name || "Tool"),
        detail: String(tool.summary || tool.impact || (tool.ok ? "Completed" : "Failed")),
      });
    }

    const stages = (workflow?.stages as string[]) || [];
    for (const [i, stage] of stages.entries()) {
      out.push({
        id: `stage-${i}`,
        kind: "events",
        timestamp: "—",
        title: "Pipeline stage",
        detail: stage,
      });
    }

    const evidence = report?.evidence_analysis?.length
      ? report.evidence_analysis
      : (retrieved || []).map((r, i) => ({
          label: r.chunk_id || `[E${i + 1}]`,
          message: r.text,
          timestamp: String(r.metadata?.timestamp || ""),
          chat: String(r.metadata?.chat_title || r.metadata?.chat_id || ""),
          sender: String(r.metadata?.sender_id || ""),
          intent_classification: "Unknown",
          intent_confidence_pct: Math.round((r.score || 0) * 100),
        }));

    for (const [i, row] of evidence.entries()) {
      out.push({
        id: `msg-${i}`,
        kind: "messages",
        timestamp: row.timestamp || "—",
        title: row.label || `Message ${i + 1}`,
        detail: (row.message || "").slice(0, 220),
        band: row.intent_classification,
      });
    }

    const edges = report?.network_analysis?.edges || [];
    for (const [i, edge] of edges.entries()) {
      out.push({
        id: `rel-${i}`,
        kind: "relationships",
        timestamp: "—",
        title: String(edge.title || edge.type || edge.chat_id || `Edge ${i + 1}`),
        detail: String(
          edge.summary ||
            `Messages: ${edge.message_count ?? "—"} · Suspicious: ${edge.suspicious_count ?? 0}`,
        ),
      });
    }

    if (edges.length === 0 && report?.network_analysis?.summary) {
      out.push({
        id: "rel-summary",
        kind: "relationships",
        timestamp: "—",
        title: "Network summary",
        detail: report.network_analysis.summary,
      });
    }

    return out;
  }, [report, retrieved, workflow]);

  const filtered = rows.filter((r) => r.kind === tab);

  return (
    <section className="investigation-timeline" aria-label="Investigation timeline">
      <header className="investigation-timeline-head">
        <h3>
          {focus === "network"
            ? "Network"
            : focus === "behavior"
              ? "Behavior evidence"
              : focus === "alerts"
                ? "Alert evidence"
                : "Evidence trail"}
        </h3>
        <div className="investigation-timeline-tabs" role="tablist">
          {tabOptions.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`investigation-timeline-tab${tab === id ? " active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {filtered.length === 0 ? (
        <p className="caption investigation-timeline-empty">No {tab} in this investigation yet.</p>
      ) : (
        <ol className="investigation-timeline-list">
          {filtered.map((row) => (
            <li key={row.id} className="investigation-timeline-item">
              <span className="investigation-timeline-time">{row.timestamp}</span>
              <span className="investigation-timeline-body">
                <strong>{row.title}</strong>
                {row.band ? (
                  <span className={`investigation-timeline-band ${riskBandClass("MEDIUM")}`}>
                    {row.band}
                  </span>
                ) : null}
                <span className="investigation-timeline-detail">{row.detail}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
