"use client";

import { getQuickAction } from "./types";

type Props = {
  actionId: string;
  onClear?: () => void;
  onFocusSearch?: () => void;
};

export function ActionBriefPanel({ actionId, onClear, onFocusSearch }: Props) {
  const action = getQuickAction(actionId);
  if (!action) return null;

  return (
    <section className="ai-action-brief" aria-label={`${action.label} ready`}>
      <div className="ai-action-brief-head">
        <p className="ai-action-brief-kicker">Investigation type</p>
        <h2>{action.label}</h2>
        {onClear ? (
          <button
            type="button"
            className="btn ai-btn-ghost ai-action-brief-clear"
            onClick={onClear}
            aria-label="Clear investigation type"
          >
            Clear
          </button>
        ) : null}
      </div>
      <p className="ai-action-brief-desc">{action.description}</p>
      <p className="ai-action-brief-hint">
        <strong>Next:</strong> {action.targetHint}
      </p>
      {onFocusSearch ? (
        <button type="button" className="btn primary" onClick={onFocusSearch}>
          Enter target
        </button>
      ) : null}
    </section>
  );
}
