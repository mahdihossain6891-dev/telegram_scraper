"use client";

import { SUGGESTED_NEXT_STEPS } from "./types";

type Props = {
  busy: boolean;
  onAction: (prompt: string, actionId: string) => void;
};

export function SuggestedActions({ busy, onAction }: Props) {
  return (
    <section className="ai-next-steps" aria-label="Suggested next steps">
      <h3>Suggested next steps</h3>
      <div className="ai-next-grid">
        {SUGGESTED_NEXT_STEPS.map((step) => (
          <button
            key={step.id}
            type="button"
            className="ai-next-card"
            disabled={busy}
            title={step.description}
            onClick={() => onAction(step.prompt, step.actionId)}
          >
            <span className="ai-next-label">{step.label}</span>
            <span className="ai-next-desc">{step.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
