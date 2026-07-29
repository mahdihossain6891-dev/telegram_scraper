"use client";

import { useMemo, useState } from "react";

import type { ChatSummaryRow, MessageDisplayRow } from "@/lib/types";

type SourcesPageProps = {
  chatSummaries: ChatSummaryRow[];
  messages: MessageDisplayRow[];
};

function typeBadge(chatType: string) {
  const t = chatType.toLowerCase();
  if (t === "channel") return "channel";
  if (t === "private chat") return "private";
  return "group";
}

export function SourcesPage({ chatSummaries, messages }: SourcesPageProps) {
  const [selectedId, setSelectedId] = useState<number | null>(
    chatSummaries[0]?.chat_id ?? null,
  );

  const selected = useMemo(
    () => chatSummaries.find((c) => c.chat_id === selectedId) ?? null,
    [chatSummaries, selectedId],
  );

  const sourceMessages = useMemo(() => {
    if (selectedId == null) return [];
    return messages.filter((m) => m.chat_id === selectedId).slice(0, 40);
  }, [messages, selectedId]);

  const counts = useMemo(() => {
    let channels = 0;
    let groups = 0;
    let privateDms = 0;
    for (const c of chatSummaries) {
      const t = typeBadge(c.chat_type);
      if (t === "channel") channels += 1;
      else if (t === "private") privateDms += 1;
      else groups += 1;
    }
    return { channels, groups, privateDms };
  }, [chatSummaries]);

  return (
    <>
      <div className="page-header">
        <h1>Channels</h1>
        <p>Collection inventory — channels, groups, and private DMs under watch.</p>
      </div>

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
          <div className="metric-value">{counts.privateDms}</div>
        </div>
        <div className="metric-card tone-primary">
          <div className="metric-label">Flagged volume</div>
          <div className="metric-value">
            {chatSummaries.reduce((s, c) => s + c.messages, 0)}
          </div>
        </div>
      </div>

      <div className="personnel-layout">
        <section className="panel card">
          <h2>Collection sources ({chatSummaries.length})</h2>
          {!chatSummaries.length ? (
            <div className="empty-state">No sources in current filters.</div>
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
                      className={
                        selectedId === chat.chat_id ? "personnel-row active" : "personnel-row"
                      }
                      onClick={() => setSelectedId(chat.chat_id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedId(chat.chat_id);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-pressed={selectedId === chat.chat_id}
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
                          {chat.risk_level || "Low"} · {chat.risk_score ?? 0}
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
            <div className="empty-state">Select a source to inspect flagged intel.</div>
          ) : (
            <>
              <div className="personnel-detail-head">
                <div>
                  <h2>{selected.title}</h2>
                  <p className="caption">
                    {selected.chat_type} · {selected.messages} flagged · narcotics{" "}
                    {selected.narcotics} · trafficking {selected.human_trafficking} · firearms{" "}
                    {selected.firearms}
                  </p>
                </div>
              </div>
              <div className="message-history">
                {!sourceMessages.length ? (
                  <div className="empty-state">No flagged messages for this source.</div>
                ) : (
                  sourceMessages.map((row) => (
                    <article key={`${row.chat_id}-${row.message_id}`} className="message-card">
                      <div className="message-meta">
                        <code>{row.timestamp.replace("T", " ").slice(0, 19)}</code>
                        <span>{row.sender}</span>
                        <span
                          className={`risk-badge risk-${String(row.risk_level || "Low").toLowerCase()}`}
                        >
                          {row.risk_level}
                        </span>
                      </div>
                      <p>{row.text || "(no text)"}</p>
                      <div className="caption">flags: {row.keywords || "—"}</div>
                    </article>
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
