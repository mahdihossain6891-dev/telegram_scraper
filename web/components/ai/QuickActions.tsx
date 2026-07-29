"use client";

import { QUICK_ACTIONS } from "./types";

type Props = {
  busy: boolean;
  activeActionId?: string | null;
  onAction: (actionId: string) => void;
};

export function QuickActions({ busy, activeActionId, onAction }: Props) {
  return (
    <div className="ai-quick-actions" role="group" aria-label="Quick investigation actions">
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.id}
          type="button"
          className={
            activeActionId === action.id ? "ai-quick-btn active" : "ai-quick-btn"
          }
          disabled={busy}
          title={action.description}
          aria-pressed={activeActionId === action.id}
          onClick={() => onAction(action.id)}
        >
          <span className="ai-quick-btn-label">{action.label}</span>
        </button>
      ))}
    </div>
  );
}
