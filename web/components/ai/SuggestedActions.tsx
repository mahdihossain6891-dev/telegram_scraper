"use client";

import { SUGGESTED_NEXT_STEPS } from "./types";

type Props = {
  busy: boolean;
  onAction: (prompt: string) => void;
};

export function SuggestedActions({ busy, onAction }: Props) {
  return (
    <section className="ai-next-steps" aria-label="Suggested next steps">
      <h3>Suggested Next Steps</h3>
      <div className="ai-next-grid">
        {SUGGESTED_NEXT_STEPS.map((step) => (
          <button
            key={step.id}
            type="button"
            className="ai-next-card"
            disabled={busy}
            onClick={() => onAction(step.prompt)}
          >
            {step.label}
          </button>
        ))}
      </div>
    </section>
  );
}
