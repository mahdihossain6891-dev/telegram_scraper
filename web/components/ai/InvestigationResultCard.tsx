"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  EntityNoMatchPanel,
  EntitySelectionPanel,
} from "@/components/ai/EntitySelectionPanel";
import { InvestigationMetricsGrid } from "@/components/ai/InvestigationMetricsGrid";
import { InvestigationTimeline } from "@/components/ai/InvestigationTimeline";
import type { ChatMessage, EntityCandidate } from "./types";
import { confidenceClass, dedupeEntityCandidates, parseInvestigationSections } from "./utils";

type Props = {
  query: string;
  message: ChatMessage;
  busy?: boolean;
  onShowEvidence: () => void;
  onSelectEntity?: (candidate: EntityCandidate, originalQuery: string) => void;
};

function isAmbiguousStatus(status?: string, content?: string): boolean {
  const s = (status || "").toLowerCase();
  return (
    s === "ambiguous" ||
    s === "ambiguous match" ||
    /did you mean/i.test(content || "") ||
    /multiple matches/i.test(content || "")
  );
}

function isNoMatchStatus(status?: string, content?: string): boolean {
  const s = (status || "").toLowerCase();
  return (
    s === "no_match" ||
    s === "no match found" ||
    s === "target_required" ||
    s === "target required" ||
    /no match found/i.test(content || "") ||
    /no monitored user/i.test(content || "") ||
    /no investigation target selected/i.test(content || "")
  );
}

export function InvestigationResultCard({
  query,
  message,
  busy,
  onShowEvidence,
  onSelectEntity,
}: Props) {
  const er = message.entityResolution;
  const isNoMatch = isNoMatchStatus(er?.status, message.content);
  const isAmbiguous = isAmbiguousStatus(er?.status, message.content);
  const [selectedId, setSelectedId] = useState<string | number | null>(null);
  const autoSelectedRef = useRef(false);
  const uniqueCandidates = useMemo(
    () => dedupeEntityCandidates(er?.candidates || []),
    [er?.candidates],
  );
  const sections =
    isNoMatch || isAmbiguous ? [] : parseInvestigationSections(message.content);
  const unmatched = er?.unmatched_query || query;

  // If duplicates collapsed to a single Telegram identity, auto-investigate.
  useEffect(() => {
    if (!isAmbiguous || !onSelectEntity || busy || selectedId != null) return;
    if (autoSelectedRef.current) return;
    if (uniqueCandidates.length !== 1) return;
    const only = uniqueCandidates[0];
    if (only.entity_id == null) return;
    autoSelectedRef.current = true;
    setSelectedId(only.entity_id);
    onSelectEntity(only, query);
  }, [isAmbiguous, onSelectEntity, busy, selectedId, uniqueCandidates, query]);

  const isTargetRequired =
    (er?.status || "").toLowerCase().includes("target") ||
    /no investigation target selected/i.test(message.content || "");

  return (
    <article
      className={`ai-result-card${message.refused ? " refused" : ""}${
        isNoMatch ? " ai-result-nomatch" : ""
      }${isAmbiguous ? " ai-result-ambiguous" : ""}`}
      aria-label="Investigation result"
    >
      <header className="ai-result-head">
        <div>
          <p className="ai-result-query-label">Investigation</p>
          <h2 className="ai-result-query">{query}</h2>
        </div>
        <div className="ai-result-badges">
          {isNoMatch ? (
            <span className="ai-conf ai-conf-low">
              {isTargetRequired ? "Target Required" : "No Match Found"}
            </span>
          ) : null}
          {isAmbiguous ? (
            <span className="ai-conf ai-conf-medium">Select Entity</span>
          ) : null}
          {!isNoMatch && !isAmbiguous && message.confidence ? (
            <span className={confidenceClass(message.confidence)}>{message.confidence}</span>
          ) : null}
          {message.intent ? <span className="ai-intent">{message.intent}</span> : null}
          {message.model ? <span className="caption">{message.model}</span> : null}
        </div>
      </header>

      {isNoMatch ? (
        isTargetRequired ? (
          <section className="ai-entity-nomatch" aria-label="Target required">
            <h3>No investigation target selected</h3>
            <p>
              Please search for and select a monitored user before starting an
              investigation.
            </p>
            <p className="caption">Suggestions:</p>
            <ul>
              {(er?.suggestions && er.suggestions.length > 0
                ? er.suggestions
                : [
                    "Search for a monitored user",
                    "Enter @username or Telegram ID",
                    "Select an entity from matching results",
                  ]
              ).map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </section>
        ) : (
          <EntityNoMatchPanel
            queryLabel={unmatched}
            suggestions={er?.suggestions}
          />
        )
      ) : null}

      {isAmbiguous && uniqueCandidates.length > 0 && onSelectEntity ? (
        selectedId != null && !busy ? (
          <p className="caption ai-entity-selected-note">
            Entity selected — investigation started.
          </p>
        ) : uniqueCandidates.length === 1 ? (
          <p className="caption ai-entity-selected-note">
            Unique match found — starting investigation…
          </p>
        ) : (
          <EntitySelectionPanel
            queryLabel={unmatched || query}
            candidates={uniqueCandidates}
            busy={busy}
            selectedId={selectedId}
            onSelect={(candidate) => {
              setSelectedId(candidate.entity_id ?? null);
              onSelectEntity(candidate, query);
            }}
          />
        )
      ) : null}

      {!isNoMatch && !isAmbiguous ? (
        <>
          {message.threatReport ? (
            <InvestigationMetricsGrid
              report={message.threatReport}
              retrieved={message.retrieved}
              confidence={message.confidence}
            />
          ) : null}
          <InvestigationTimeline
            report={message.threatReport || null}
            retrieved={message.retrieved}
            workflow={message.workflow}
          />
          <div className="ai-result-sections">
            {sections.map((section) => (
              <section
                key={section.id}
                className={`ai-result-section ai-section-${section.id}`}
              >
                <h3>{section.title}</h3>
                <p>{section.body}</p>
              </section>
            ))}
          </div>
        </>
      ) : null}

      {!isNoMatch &&
      !isAmbiguous &&
      message.citations &&
      message.citations.length > 0 ? (
        <div className="ai-cite-row">
          {message.citations.map((c, i) => (
            <button
              key={`${c.source_id}-${i}`}
              type="button"
              className="ai-cite-chip"
              title={c.snippet}
              onClick={onShowEvidence}
            >
              {c.label || `${c.source_type}:${c.source_id}`}
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}
