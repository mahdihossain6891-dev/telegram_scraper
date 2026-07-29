"use client";

import { useEffect, useMemo, useState } from "react";

import {
  buildPersonnelDetailFromPayload,
  buildPersonnelFromPayload,
  filterAndSortPersonnel,
  highlightKeywords,
} from "@/lib/personnel";
import { enrichPersonnelRisk } from "@/lib/risk";
import {
  buildSuspectTimeline,
  eventKindLabel,
  type TimelineEvent,
} from "@/lib/timeline";
import type { ExportPayload } from "@/lib/types";

type CasesPageProps = {
  payload: ExportPayload;
};

type CaseTab = "timeline" | "profile" | "risk";

function eventTone(kind: TimelineEvent["kind"]): string {
  switch (kind) {
    case "joined":
      return "joined";
    case "media":
      return "media";
    case "contact":
      return "contact";
    case "keyword":
      return "keyword";
    default:
      return "flagged";
  }
}

export function CasesPage({ payload }: CasesPageProps) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<CaseTab>("timeline");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const suspects = useMemo(
    () =>
      filterAndSortPersonnel(buildPersonnelFromPayload(payload).map(enrichPersonnelRisk), {
        chatId: null,
        suspiciousOnly: true,
        keyword: "",
        query,
        dateFrom: "",
        dateTo: "",
        useDateFilter: false,
        sortBy: "suspicious_count",
      }).sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0)),
    [payload, query],
  );

  useEffect(() => {
    if (!suspects.length) {
      setSelectedUserId(null);
      return;
    }
    if (selectedUserId == null || !suspects.some((s) => s.user_id === selectedUserId)) {
      setSelectedUserId(suspects[0].user_id);
    }
  }, [suspects, selectedUserId]);

  const timeline = useMemo(() => {
    if (selectedUserId == null) return null;
    return buildSuspectTimeline(payload, selectedUserId);
  }, [payload, selectedUserId]);

  const detail = useMemo(() => {
    if (selectedUserId == null) return null;
    return buildPersonnelDetailFromPayload(payload, selectedUserId);
  }, [payload, selectedUserId]);

  const selected = suspects.find((s) => s.user_id === selectedUserId) ?? null;

  return (
    <>
      <div className="page-header">
        <h1>Users</h1>
        <p>Suspect dossiers — risk score, profile, and criminal timeline in one investigation pane.</p>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">Open cases</div>
          <div className="metric-value">{suspects.length}</div>
        </div>
        <div className="metric-card tone-danger">
          <div className="metric-label">Critical / High</div>
          <div className="metric-value">
            {
              suspects.filter((s) => s.risk_level === "Critical" || s.risk_level === "High")
                .length
            }
          </div>
        </div>
        <div className="metric-card tone-accent">
          <div className="metric-label">Timeline events</div>
          <div className="metric-value">{timeline?.events.length ?? 0}</div>
        </div>
      </div>

      <div className="timeline-layout">
        <section className="panel card timeline-suspects">
          <div className="timeline-suspects-head">
            <h2>Suspects</h2>
            <input
              type="search"
              placeholder="Search name or ID…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search suspects"
            />
          </div>
          {!suspects.length ? (
            <div className="empty-state">No cases match.</div>
          ) : (
            <ul className="suspect-list">
              {suspects.map((row) => {
                const active = selectedUserId === row.user_id;
                return (
                  <li key={row.user_id}>
                    <button
                      type="button"
                      className={active ? "suspect-card active" : "suspect-card"}
                      onClick={() => setSelectedUserId(row.user_id)}
                      aria-pressed={active}
                    >
                      <div className="suspect-card-top">
                        <strong>{row.display_name}</strong>
                        <span
                          className={`risk-badge risk-${String(row.risk_level || "Low").toLowerCase()}`}
                        >
                          {row.risk_level} · {row.risk_score ?? 0}
                        </span>
                      </div>
                      <div className="caption">
                        {row.username ? `@${row.username}` : `ID ${row.user_id}`} ·{" "}
                        {row.suspicious_count} flagged
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="panel card timeline-panel">
          {!selected || !timeline || !detail ? (
            <div className="empty-state">Select a suspect to open the case file.</div>
          ) : (
            <>
              <div className="timeline-panel-head">
                <div>
                  <h2>{selected.display_name}</h2>
                  <p className="caption">
                    {selected.username ? `@${selected.username}` : "no username"} · ID{" "}
                    <code>{selected.user_id}</code>
                  </p>
                </div>
                <div className="tab-row" role="tablist" aria-label="Case views">
                  {(
                    [
                      ["timeline", "Timeline"],
                      ["profile", "Profile"],
                      ["risk", "Risk"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      role="tab"
                      className={tab === id ? "tab-btn active" : "tab-btn"}
                      aria-selected={tab === id}
                      onClick={() => setTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {tab === "timeline" ? (
                <ol className="criminal-timeline">
                  {timeline.days.map((day) => (
                    <li key={day.date_key} className="timeline-day">
                      <div className="timeline-day-label">{day.label}</div>
                      <ol className="timeline-events">
                        {day.events.map((event) => (
                          <li
                            key={event.id}
                            className={`timeline-event tone-${eventTone(event.kind)}`}
                          >
                            <div className="timeline-marker" aria-hidden="true" />
                            <article className="timeline-event-body">
                              <div className="timeline-event-meta">
                                <span className={`event-kind kind-${event.kind}`}>
                                  {eventKindLabel(event.kind)}
                                </span>
                                <span className="caption">{event.group_name}</span>
                              </div>
                              <h3 className="timeline-event-title">{event.title}</h3>
                              {event.detail ? (
                                <p
                                  className="timeline-event-detail"
                                  dangerouslySetInnerHTML={{
                                    __html: highlightKeywords(event.detail, event.keywords),
                                  }}
                                />
                              ) : null}
                            </article>
                          </li>
                        ))}
                      </ol>
                    </li>
                  ))}
                </ol>
              ) : null}

              {tab === "profile" ? (
                <>
                  <div className="metric-grid compact">
                    <div className="metric-card">
                      <div className="metric-label">Messages</div>
                      <div className="metric-value">{detail.summary.message_count}</div>
                    </div>
                    <div className="metric-card tone-danger">
                      <div className="metric-label">Suspicious</div>
                      <div className="metric-value">{detail.summary.suspicious_count}</div>
                    </div>
                    <div className="metric-card tone-accent">
                      <div className="metric-label">Groups</div>
                      <div className="metric-value">{detail.groups.length}</div>
                    </div>
                  </div>
                  <h3>Observed sources</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Source</th>
                          <th>Msgs</th>
                          <th>First</th>
                          <th>Latest</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.groups.map((g) => (
                          <tr key={g.chat_id}>
                            <td>{g.group_name}</td>
                            <td>{g.suspicious_count}</td>
                            <td>{g.first_seen?.slice(0, 10) || "—"}</td>
                            <td>{g.last_seen?.slice(0, 10) || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <h3>Keywords</h3>
                  <div className="chip-row">
                    {Object.entries(detail.keyword_frequency).map(([kw, count]) => (
                      <span key={kw} className="chip">
                        {kw} <strong>{count}</strong>
                      </span>
                    ))}
                  </div>
                </>
              ) : null}

              {tab === "risk" ? (
                <>
                  <div className="metric-grid compact">
                    <div className="metric-card tone-danger">
                      <div className="metric-label">Score</div>
                      <div className="metric-value">{selected.risk_score ?? 0}</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">Level</div>
                      <div className="metric-value small">{selected.risk_level || "Low"}</div>
                    </div>
                  </div>
                  <h3>Risk factors</h3>
                  {!selected.risk_factors?.length ? (
                    <div className="empty-state">No scored factors yet.</div>
                  ) : (
                    <ul className="steps-list">
                      {selected.risk_factors.map((factor) => (
                        <li key={factor}>{factor}</li>
                      ))}
                    </ul>
                  )}
                  <h3>Score bands</h3>
                  <div className="settings-grid">
                    <div>
                      <span>0–20</span>
                      <strong>Low</strong>
                    </div>
                    <div>
                      <span>21–40</span>
                      <strong>Medium</strong>
                    </div>
                    <div>
                      <span>41–70</span>
                      <strong>High</strong>
                    </div>
                    <div>
                      <span>71–100</span>
                      <strong>Critical</strong>
                    </div>
                  </div>
                </>
              ) : null}
            </>
          )}
        </section>
      </div>
    </>
  );
}
