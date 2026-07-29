"use client";

import { useMemo, useState } from "react";

import { downloadText, rowsToCsv } from "@/lib/csv";
import { CONTENT_ENTITY_TYPES, KEYWORD_ENTITY_TYPES, LINK_ENTITY_TYPES } from "@/lib/constants";
import type { EntityDisplayRow, MessageDisplayRow } from "@/lib/types";

type IntelPageProps = {
  messages: MessageDisplayRow[];
  entities: EntityDisplayRow[];
};

type IntelTab = "messages" | "entities";

export function IntelPage({ messages, entities }: IntelPageProps) {
  const [tab, setTab] = useState<IntelTab>("messages");
  const [query, setQuery] = useState("");
  const [entityView, setEntityView] = useState("All entities");
  const [limit, setLimit] = useState(100);

  const filteredMessages = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = messages;
    if (q) {
      rows = rows.filter(
        (row) =>
          row.text.toLowerCase().includes(q) ||
          row.keywords.toLowerCase().includes(q) ||
          row.sender.toLowerCase().includes(q) ||
          row.chat.toLowerCase().includes(q),
      );
    }
    return rows.slice(0, limit);
  }, [messages, query, limit]);

  const filteredEntities = useMemo(() => {
    let rows = entities;
    if (entityView === "Links & contacts") {
      rows = rows.filter((e) => LINK_ENTITY_TYPES.has(e.entity_type));
    } else if (entityView === "Keyword flags only") {
      rows = rows.filter((e) => KEYWORD_ENTITY_TYPES.has(e.entity_type));
    }
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (e) =>
          e.entity_value.toLowerCase().includes(q) ||
          e.entity_type.toLowerCase().includes(q) ||
          e.chat.toLowerCase().includes(q),
      );
    }
    return rows.slice(0, limit);
  }, [entities, entityView, query, limit]);

  return (
    <>
      <div className="page-header">
        <h1>Threat Monitoring</h1>
        <p>Evidence layer — searchable flagged messages and extracted entities.</p>
      </div>

      <div className="controls-row">
        <label>
          Search intel
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Keyword, sender, source, entity…"
          />
        </label>
        <label>
          Max rows
          <input
            type="number"
            min={20}
            max={500}
            step={20}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </label>
        <div className="tab-row" role="tablist">
          <button
            type="button"
            className={tab === "messages" ? "tab-btn active" : "tab-btn"}
            onClick={() => setTab("messages")}
          >
            Messages ({filteredMessages.length})
          </button>
          <button
            type="button"
            className={tab === "entities" ? "tab-btn active" : "tab-btn"}
            onClick={() => setTab("entities")}
          >
            Entities ({filteredEntities.length})
          </button>
        </div>
      </div>

      {tab === "entities" ? (
        <div className="filter-chips" role="radiogroup" aria-label="Entity view">
          {["All entities", "Links & contacts", "Keyword flags only"].map((option) => (
            <button
              key={option}
              type="button"
              className={entityView === option ? "filter-chip active" : "filter-chip"}
              aria-pressed={entityView === option}
              onClick={() => setEntityView(option)}
            >
              {option}
            </button>
          ))}
        </div>
      ) : null}

      <section className="panel card">
        <div className="panel-head">
          <h2>{tab === "messages" ? "Flagged messages" : "Extracted entities"}</h2>
          <button
            type="button"
            className="btn"
            onClick={() => {
              if (tab === "messages") {
                downloadText(
                  "intel_messages.csv",
                  rowsToCsv(filteredMessages as unknown as Record<string, unknown>[]),
                  "text/csv",
                );
              } else {
                downloadText(
                  "intel_entities.csv",
                  rowsToCsv(filteredEntities as unknown as Record<string, unknown>[]),
                  "text/csv",
                );
              }
            }}
          >
            Download CSV
          </button>
        </div>

        {tab === "messages" ? (
          !filteredMessages.length ? (
            <div className="empty-state">No messages match.</div>
          ) : (
            <div className="table-wrap tall">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Sender</th>
                    <th>Keywords</th>
                    <th>Risk</th>
                    <th>Text</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMessages.map((row) => (
                    <tr key={`${row.chat_id}-${row.message_id}`}>
                      <td className="mono">{row.timestamp.slice(0, 16).replace("T", " ")}</td>
                      <td>{row.chat}</td>
                      <td>{row.sender}</td>
                      <td>{row.keywords || "—"}</td>
                      <td>
                        <span
                          className={`risk-badge risk-${String(row.risk_level || "Low").toLowerCase()}`}
                        >
                          {row.risk_level}
                        </span>
                      </td>
                      <td className="intel-text">{row.text || "(no text)"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : !filteredEntities.length ? (
          <div className="empty-state">No entities match.</div>
        ) : (
          <div className="table-wrap tall">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Source</th>
                  <th>Time</th>
                  <th>Kind</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntities.map((row, index) => (
                  <tr key={`${row.entity_type}-${row.entity_value}-${index}`}>
                    <td>
                      <span
                        className={`source-badge type-${
                          KEYWORD_ENTITY_TYPES.has(row.entity_type)
                            ? "channel"
                            : CONTENT_ENTITY_TYPES.has(row.entity_type)
                              ? "private"
                              : "group"
                        }`}
                      >
                        {row.entity_type}
                      </span>
                    </td>
                    <td>{row.entity_value}</td>
                    <td>{row.chat}</td>
                    <td className="mono">{String(row.timestamp).slice(0, 16).replace("T", " ")}</td>
                    <td>
                      {KEYWORD_ENTITY_TYPES.has(row.entity_type)
                        ? "keyword"
                        : LINK_ENTITY_TYPES.has(row.entity_type)
                          ? "contact"
                          : "other"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
