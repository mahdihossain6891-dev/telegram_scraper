"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { EntityCandidate } from "./types";
import { dedupeEntityCandidates } from "./utils";

type Props = {
  queryLabel: string;
  candidates: EntityCandidate[];
  busy?: boolean;
  selectedId?: string | number | null;
  onSelect: (candidate: EntityCandidate) => void;
};

function initials(candidate: EntityCandidate): string {
  const name = (candidate.display_name || candidate.label || "").trim();
  if (!name || name.startsWith("@") || name.startsWith("Unknown")) {
    const handle = (candidate.username || "").replace(/^@/, "");
    if (handle) return handle.slice(0, 2).toUpperCase();
    return "??";
  }
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function riskLabel(candidate: EntityCandidate): { text: string; level: string } {
  const explicit = (candidate.risk_level || "").toString().trim();
  if (explicit) {
    const low = explicit.toLowerCase();
    if (low.includes("high") || low.includes("critical")) return { text: "High", level: "high" };
    if (low.includes("medium")) return { text: "Medium", level: "medium" };
    if (low.includes("low")) return { text: "Low", level: "low" };
    return { text: explicit, level: "unknown" };
  }
  const score = candidate.risk_score;
  if (score == null) return { text: "Unknown", level: "unknown" };
  if (score >= 70) return { text: "High", level: "high" };
  if (score >= 40) return { text: "Medium", level: "medium" };
  return { text: "Low", level: "low" };
}

function formatLastSeen(value: string | null | undefined): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export function EntitySelectionPanel({
  queryLabel,
  candidates,
  busy,
  selectedId,
  onSelect,
}: Props) {
  const [filter, setFilter] = useState("");
  const [focusIndex, setFocusIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const unique = dedupeEntityCandidates(candidates);
    const q = filter.trim().toLowerCase();
    if (!q) return unique;
    return unique.filter((c) => {
      const hay = [
        c.display_name,
        c.label,
        c.username,
        c.first_name,
        c.last_name,
        String(c.entity_id ?? ""),
        c.entity_type,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [candidates, filter]);

  useEffect(() => {
    setFocusIndex(0);
  }, [filter, candidates.length]);

  const focusCard = (index: number) => {
    setFocusIndex(index);
    requestAnimationFrame(() => {
      const el = listRef.current?.querySelector<HTMLElement>(
        `[data-entity-index="${index}"]`,
      );
      el?.focus();
    });
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (!filtered.length) return;
    const target = e.target as HTMLElement | null;
    if (target?.tagName === "INPUT") {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        focusCard(0);
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      focusCard(Math.min(filtered.length - 1, focusIndex + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      focusCard(Math.max(0, focusIndex - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = filtered[focusIndex];
      if (pick && !busy) onSelect(pick);
    }
  };

  return (
    <section
      className="ai-entity-panel"
      aria-label="Select entity to investigate"
      onKeyDown={onKeyDown}
    >
      <header className="ai-entity-panel-head">
        <div>
          <h3>Multiple matches found</h3>
          <p className="caption">
            Select a monitored entity for “{queryLabel}”. Investigation starts immediately.
          </p>
        </div>
        {candidates.length > 4 ? (
          <label className="ai-entity-filter">
            <span className="sr-only">Filter entities</span>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by name, @username, or ID…"
              disabled={busy}
            />
          </label>
        ) : null}
      </header>

      {filtered.length === 0 ? (
        <p className="caption ai-empty">No entities match this filter.</p>
      ) : (
        <div className="ai-entity-card-grid" ref={listRef} role="listbox">
          {filtered.map((c, index) => {
            const risk = riskLabel(c);
            const lastSeen = formatLastSeen(c.last_seen);
            const id = c.entity_id;
            const isSelected = selectedId != null && String(selectedId) === String(id);
            const title = c.display_name || c.label || `Entity ${id}`;
            const handle = c.username
              ? c.username.startsWith("@")
                ? c.username
                : `@${c.username}`
              : null;
            return (
              <button
                key={`${c.entity_type || "entity"}-${id}-${index}`}
                type="button"
                role="option"
                aria-selected={isSelected || focusIndex === index}
                data-entity-index={index}
                className={`ai-entity-pick-card${isSelected ? " selected" : ""}${
                  focusIndex === index ? " focused" : ""
                }`}
                disabled={busy}
                onClick={() => onSelect(c)}
                onFocus={() => setFocusIndex(index)}
              >
                <span className="ai-entity-avatar" aria-hidden="true">
                  {initials(c)}
                </span>
                <span className="ai-entity-pick-body">
                  <span className="ai-entity-pick-title">{title}</span>
                  {handle ? <span className="ai-entity-pick-user">{handle}</span> : null}
                  <span className="ai-entity-pick-meta">
                    <span className={`ai-risk-pill ai-risk-${risk.level}`}>
                      Risk: {risk.text}
                    </span>
                    {id != null ? (
                      <span className="caption">Telegram ID: {String(id)}</span>
                    ) : null}
                  </span>
                  {lastSeen ? (
                    <span className="caption">Last seen: {lastSeen}</span>
                  ) : null}
                </span>
                <span className="btn primary ai-entity-pick-action">
                  {isSelected ? "Selected…" : "Investigate"}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

type NoMatchProps = {
  queryLabel: string;
  suggestions?: string[];
};

export function EntityNoMatchPanel({ queryLabel, suggestions }: NoMatchProps) {
  const tips =
    suggestions && suggestions.length > 0
      ? suggestions
      : ["Check spelling", "Search by username", "Search by Telegram ID"];

  return (
    <section className="ai-entity-nomatch" aria-label="No entity match">
      <h3>No monitored user found</h3>
      <p>
        No monitored user, group, or channel matching <strong>{queryLabel}</strong> was
        found.
      </p>
      <p className="caption">Suggestions:</p>
      <ul>
        {tips.map((tip) => (
          <li key={tip}>{tip}</li>
        ))}
      </ul>
    </section>
  );
}
