"use client";

import { IconSpark } from "./icons";
import { SUGGESTED_PROMPTS } from "./types";

type Props = {
  onSelectAction: (actionId: string) => void;
};

export function EmptyState({ onSelectAction }: Props) {
  return (
    <div className="ai-empty-state">
      <div className="ai-empty-icon" aria-hidden="true">
        <IconSpark />
      </div>
      <h2>Welcome to Sébastien</h2>
      <p className="ai-tagline">AI Investigation Copilot</p>
      <p className="ai-empty-copy">
        Sébastien assists cybersecurity analysts by analyzing retrieved evidence and producing
        grounded intelligence summaries — not free-form chat. Choose an investigation type, then
        search for a monitored user or entity.
      </p>
      <div className="ai-suggest-grid">
        {SUGGESTED_PROMPTS.map((item) => (
          <button
            key={item.id}
            type="button"
            className="ai-suggest-card"
            onClick={() => onSelectAction(item.actionId)}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
