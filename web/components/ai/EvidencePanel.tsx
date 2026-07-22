"use client";

import type { AiCitation, AiRetrieved, Confidence } from "./types";
import { confidenceClass } from "./utils";
import { IconChevron, IconPanelToggle } from "./icons";

type Props = {
  citations: AiCitation[];
  retrieved: AiRetrieved[];
  confidence?: Confidence;
  collapsed?: boolean;
  cardOpen?: Record<string, boolean>;
  onCardOpenChange?: (next: Record<string, boolean>) => void;
  onToggleCollapse?: () => void;
};

function metaField(meta: Record<string, unknown> | undefined, key: string): string | null {
  if (!meta) return null;
  const v = meta[key];
  if (v == null) return null;
  if (typeof v === "string" || typeof v === "number") return String(v);
  return null;
}

function retrievedItemId(item: AiRetrieved, index: number): string {
  const chunk =
    (item.chunk_id && String(item.chunk_id).trim()) ||
    metaField(item.metadata, "source_id") ||
    metaField(item.metadata, "label") ||
    `idx-${index}`;
  return `ret-${chunk}-${index}`;
}

function retrievedItemLabel(item: AiRetrieved, index: number): string {
  const chunk = item.chunk_id && String(item.chunk_id).trim();
  if (chunk) return chunk;
  return (
    metaField(item.metadata, "source_id") ||
    metaField(item.metadata, "label") ||
    `Evidence ${index + 1}`
  );
}

export function EvidencePanel({
  citations,
  retrieved,
  confidence,
  collapsed,
  cardOpen = {},
  onCardOpenChange,
  onToggleCollapse,
}: Props) {
  const hasEvidence = citations.length > 0 || retrieved.length > 0;

  const isOpen = (id: string, fallback: boolean) =>
    Object.prototype.hasOwnProperty.call(cardOpen, id) ? Boolean(cardOpen[id]) : fallback;

  const toggle = (id: string, fallback: boolean) => {
    if (!onCardOpenChange) return;
    onCardOpenChange({ ...cardOpen, [id]: !isOpen(id, fallback) });
  };

  if (collapsed) {
    return (
      <aside className="ai-evidence collapsed" aria-label="Evidence panel collapsed">
        <button
          type="button"
          className="ai-evidence-rail"
          onClick={onToggleCollapse}
          aria-expanded={false}
          title="Show evidence panel"
        >
          <IconPanelToggle collapsed />
          <span className="ai-evidence-rail-label">Evidence</span>
          <span className="ai-evidence-rail-hint" aria-hidden="true">
            &lt;
          </span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="ai-evidence" aria-label="Evidence panel">
      <div className="ai-evidence-head">
        <div>
          <h2>Evidence</h2>
          <p className="caption">Grounded sources from the latest investigation</p>
        </div>
        {onToggleCollapse ? (
          <button
            type="button"
            className="btn ai-btn-ghost ai-evidence-toggle"
            onClick={onToggleCollapse}
            aria-expanded
            title="Hide evidence panel"
          >
            <IconPanelToggle collapsed={false} />
            <span>Hide</span>
          </button>
        ) : null}
      </div>

      {!hasEvidence ? (
        <p className="caption ai-empty">No evidence retrieved yet.</p>
      ) : (
        <>
          {confidence ? (
            <div className={confidenceClass(confidence)}>
              Confidence: <strong>{confidence}</strong>
            </div>
          ) : null}

          <section>
            <h3>Evidence Sources</h3>
            {citations.length === 0 ? (
              <p className="caption ai-empty">No evidence sources yet.</p>
            ) : (
              <ul className="ai-evidence-list">
                {citations.map((c, i) => {
                  const id = `cite-${c.source_id}-${i}`;
                  const open = isOpen(id, i < 3);
                  return (
                    <li key={id} className="ai-evidence-card">
                      <button
                        type="button"
                        className="ai-evidence-card-toggle"
                        onClick={() => toggle(id, i < 3)}
                        aria-expanded={open}
                      >
                        <IconChevron open={open} />
                        <span className="ai-evidence-label">
                          {c.label || `${c.source_type}:${c.source_id}`}
                        </span>
                      </button>
                      <div className="ai-evidence-meta">
                        <span>Source · {c.source_type || "—"}</span>
                        <span>ID · {c.source_id || "—"}</span>
                      </div>
                      {open ? <p>{c.snippet || "—"}</p> : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section>
            <h3>Evidence Retrieved</h3>
            {retrieved.length === 0 ? (
              <p className="caption ai-empty">No evidence retrieved yet.</p>
            ) : (
              <ul className="ai-evidence-list">
                {retrieved.map((r, i) => {
                  const id = retrievedItemId(r, i);
                  const open = isOpen(id, i < 2);
                  const ts =
                    metaField(r.metadata, "timestamp") ||
                    metaField(r.metadata, "date") ||
                    metaField(r.metadata, "created_at");
                  const risk =
                    metaField(r.metadata, "risk") ||
                    metaField(r.metadata, "risk_level") ||
                    metaField(r.metadata, "severity");
                  const collection =
                    metaField(r.metadata, "collection") ||
                    metaField(r.metadata, "source_collection") ||
                    metaField(r.metadata, "chat_title");
                  return (
                    <li key={id} className="ai-evidence-card">
                      <button
                        type="button"
                        className="ai-evidence-card-toggle"
                        onClick={() => toggle(id, i < 2)}
                        aria-expanded={open}
                      >
                        <IconChevron open={open} />
                        <span className="ai-evidence-label">{retrievedItemLabel(r, i)}</span>
                        <span className="caption">
                          score {typeof r.score === "number" ? r.score.toFixed(3) : "—"}
                        </span>
                      </button>
                      <div className="ai-evidence-meta">
                        <span>Source · chunk</span>
                        {ts ? <span>Timestamp · {ts}</span> : null}
                        {risk ? <span>Risk · {risk}</span> : null}
                        {collection ? <span>Collection · {collection}</span> : null}
                      </div>
                      {open ? <p>{r.text}</p> : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
