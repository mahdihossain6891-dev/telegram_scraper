"use client";

import type { ConversationSession, ShellView } from "./types";
import { SHELL_NAV } from "./types";
import { selectActiveCases } from "./store";
import { caseDescription, caseRisk, formatRelativeTime } from "./utils";

type Props = {
  view: ShellView;
  onViewChange: (view: ShellView) => void;
  cases: ConversationSession[];
  activeId: string | null;
  onSelectCase: (id: string) => void;
  onNewInvestigation: () => void;
};

export function InvestigationWorkspaceBar({
  view,
  onViewChange,
  cases,
  activeId,
  onSelectCase,
  onNewInvestigation,
}: Props) {
  const activeCases = selectActiveCases(cases).filter(
    (c) => c.messages.length > 0 || c.id === activeId,
  );

  return (
    <div className="ai-workspace-bar" aria-label="Sébastien workspace">
      <div className="ai-workspace-tabs" role="tablist" aria-label="Workspace views">
        {SHELL_NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className={view === item.id ? "ai-workspace-tab active" : "ai-workspace-tab"}
            aria-selected={view === item.id}
            onClick={() => onViewChange(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button type="button" className="btn ai-btn-ghost ai-new-case-btn" onClick={onNewInvestigation}>
          New Investigation
        </button>
      </div>

      {view === "investigation" && activeCases.length > 0 ? (
        <div className="ai-active-cases" aria-label="Active cases">
          <span className="ai-active-cases-label">Active cases</span>
          <ul className="ai-active-cases-list">
            {activeCases.map((session) => {
              const risk = caseRisk(session);
              return (
                <li key={session.id}>
                  <button
                    type="button"
                    className={
                      session.id === activeId ? "ai-active-case-chip active" : "ai-active-case-chip"
                    }
                    onClick={() => onSelectCase(session.id)}
                    title={caseDescription(session)}
                  >
                    <span className={`ai-risk-dot ai-risk-${risk}`} aria-hidden="true" />
                    <span className="ai-active-case-title">{session.title}</span>
                    <span className="caption">{formatRelativeTime(session.updatedAt)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
