"use client";

import { IconSpark } from "./icons";
import { SUGGESTED_PROMPTS, getQuickAction } from "./types";

type Props = {
  onSelectAction: (actionId: string) => void;
  activeActionId?: string | null;
};

export function EmptyState({ onSelectAction, activeActionId }: Props) {
  return (
    <div className="ai-empty-state">
      <div className="ai-empty-icon" aria-hidden="true">
        <IconSpark />
      </div>
      <h2>Sébastien</h2>
      <p className="ai-empty-copy">
        Choose an investigation type, then enter a monitored user, alert, or subject ID.
      </p>
      <div className="ai-suggest-grid">
        {SUGGESTED_PROMPTS.map((item) => {
          const meta = getQuickAction(item.actionId);
          const active = activeActionId === item.actionId;
          return (
            <button
              key={item.id}
              type="button"
              className={active ? "ai-suggest-card active" : "ai-suggest-card"}
              aria-pressed={active}
              onClick={() => onSelectAction(item.actionId)}
            >
              <span className="ai-suggest-label">{item.label}</span>
              <span className="ai-suggest-desc">
                {item.description || meta?.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
