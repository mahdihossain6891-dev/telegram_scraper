"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  EntityNoMatchPanel,
  EntitySelectionPanel,
} from "@/components/ai/EntitySelectionPanel";
import { InvestigationMetricsGrid } from "@/components/ai/InvestigationMetricsGrid";
import { InvestigationTimeline } from "@/components/ai/InvestigationTimeline";
import type { ChatMessage, EntityCandidate, InvestigationSectionId } from "./types";
import { intentFocus } from "./types";
import { confidenceClass, dedupeEntityCandidates, parseInvestigationSections } from "./utils";

type Props = {
  query: string;
  message: ChatMessage;
  busy?: boolean;
  onShowEvidence: () => void;
  onSelectEntity?: (candidate: EntityCandidate, originalQuery: string) => void;
};

const SECTION_PRIORITY: Record<string, InvestigationSectionId[]> = {
  risk: [
    "executive_summary",
    "risk_assessment",
    "subject_information",
    "evidence_analysis",
    "key_findings",
    "analyst_recommendation",
  ],
  behavior: [
    "behavior_analysis",
    "executive_summary",
    "key_findings",
    "evidence_analysis",
    "recommended_actions",
  ],
  alerts: [
    "evidence_analysis",
    "threat_classification",
    "executive_summary",
    "risk_assessment",
    "supporting_evidence",
  ],
  network: [
    "network_analysis",
    "executive_summary",
    "subject_information",
    "key_findings",
    "recommended_actions",
  ],
  report: [
    "executive_summary",
    "key_findings",
    "risk_assessment",
    "analyst_recommendation",
    "confidence_level",
  ],
  general: [],
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

function prioritizeSections(
  sections: ReturnType<typeof parseInvestigationSections>,
  focus: string,
) {
  const order = SECTION_PRIORITY[focus] || [];
  if (!order.length) return sections;
  const rank = new Map(order.map((id, i) => [id, i]));
  return [...sections].sort((a, b) => {
    const ra = rank.has(a.id) ? rank.get(a.id)! : 100;
    const rb = rank.has(b.id) ? rank.get(b.id)! : 100;
    return ra - rb;
  }).filter((section, _i, arr) => {
    // Keep prioritized sections first; drop low-priority noise when focused.
    if (!order.length) return true;
    if (order.includes(section.id)) return true;
    // Still keep a couple extras if we have few prioritized hits.
    const prioritizedCount = arr.filter((s) => order.includes(s.id)).length;
    return prioritizedCount < 2;
  });
}

export function InvestigationResultCard({
  query,
  message,
  busy,
  onShowEvidence,
  onSelectEntity,
}: Props) {
  const er = message.entityResolution;
  const focus = intentFocus(message.intent);
  const isNoMatch = isNoMatchStatus(er?.status, message.content);
  const isAmbiguous = isAmbiguousStatus(er?.status, message.content);
  const [selectedId, setSelectedId] = useState<string | number | null>(null);
  const autoSelectedRef = useRef(false);
  const uniqueCandidates = useMemo(
    () => dedupeEntityCandidates(er?.candidates || []),
    [er?.candidates],
  );
  const sections = useMemo(() => {
    if (isNoMatch || isAmbiguous) return [];
    return prioritizeSections(parseInvestigationSections(message.content), focus);
  }, [isNoMatch, isAmbiguous, message.content, focus]);
  const unmatched = er?.unmatched_query || query;

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

  const focusLabel =
    focus === "behavior"
      ? "Behavior analysis"
      : focus === "network"
        ? "Network analysis"
        : focus === "alerts"
          ? "Alert analysis"
          : focus === "report"
            ? "Intelligence report"
            : "Investigation";

  return (
    <article
      className={`ai-result-card ai-focus-${focus}${message.refused ? " refused" : ""}${
        isNoMatch ? " ai-result-nomatch" : ""
      }${isAmbiguous ? " ai-result-ambiguous" : ""}`}
      aria-label={`${focusLabel} result`}
    >
      <header className="ai-result-head">
        <div>
          <p className="ai-result-query-label">{focusLabel}</p>
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
        </div>
      </header>

      {isNoMatch ? (
        isTargetRequired ? (
          <section className="ai-entity-nomatch" aria-label="Target required">
            <h3>No investigation target selected</h3>
            <p className="ai-target-required-body">
              {(message.content || "")
                .split(/\n\n/)
                .map((p) => p.trim())
                .filter(Boolean)
                .slice(0, 2)
                .join(" ") ||
                "Please search for and select a monitored user before starting this investigation."}
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
              focus={focus}
            />
          ) : null}
          <InvestigationTimeline
            report={message.threatReport || null}
            retrieved={message.retrieved}
            workflow={message.workflow}
            focus={focus}
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
