"use client";

import { useState } from "react";

import { dismissServerSession } from "@/components/ai/api";
import { CaseContextMenu } from "@/components/ai/CaseContextMenu";
import { DismissCaseDialog, RenameCaseDialog } from "@/components/ai/CaseDialogs";
import {
  dismissCaseLocally,
  renameCaseLocally,
  selectActiveCases,
} from "@/components/ai/store";
import type { ConversationSession } from "@/components/ai/types";
import { caseDescription, caseRisk, formatRelativeTime } from "@/components/ai/utils";

type Props = {
  sessions: ConversationSession[];
  onOpenCase: (id: string) => void;
};

export function SavedCasesPanel({ sessions, onOpenCase }: Props) {
  const savedCases = selectActiveCases(sessions).filter((s) => s.messages.length > 0);
  const [dismissTarget, setDismissTarget] = useState<ConversationSession | null>(null);
  const [renameTarget, setRenameTarget] = useState<ConversationSession | null>(null);
  const [busy, setBusy] = useState(false);

  const confirmDismiss = async () => {
    if (!dismissTarget || busy) return;
    setBusy(true);
    const target = dismissTarget;
    try {
      if (target.serverSessionId) {
        try {
          await dismissServerSession(target.serverSessionId);
        } catch {
          // Client dismiss still proceeds — local soft-status is source of truth for UI.
        }
      }
      dismissCaseLocally(target.id);
      setDismissTarget(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="ai-cases-panel" aria-label="Saved cases">
      <h2>Saved Cases</h2>
      <p className="caption">Active investigations in this workspace.</p>
      {savedCases.length === 0 ? (
        <p className="caption ai-empty">No saved cases yet. Start an investigation.</p>
      ) : (
        <ul className="ai-cases-list">
          {savedCases.map((s) => {
            const risk = caseRisk(s);
            return (
              <li key={s.id}>
                <div className="ai-case-card">
                  <button
                    type="button"
                    className="ai-case-card-main"
                    onClick={() => onOpenCase(s.id)}
                  >
                    <span className="ai-case-row">
                      <strong>{s.title}</strong>
                      <span className={`ai-risk-pill ai-risk-${risk}`}>{risk}</span>
                    </span>
                    <span className="caption">{formatRelativeTime(s.updatedAt)}</span>
                    <span className="ai-case-desc">{caseDescription(s)}</span>
                  </button>
                  <CaseContextMenu
                    onOpen={() => onOpenCase(s.id)}
                    onRename={() => setRenameTarget(s)}
                    onDismiss={() => setDismissTarget(s)}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <DismissCaseDialog
        open={Boolean(dismissTarget)}
        caseTitle={dismissTarget?.title || ""}
        onCancel={() => setDismissTarget(null)}
        onConfirm={() => void confirmDismiss()}
      />

      <RenameCaseDialog
        open={Boolean(renameTarget)}
        initialTitle={renameTarget?.title || ""}
        onCancel={() => setRenameTarget(null)}
        onConfirm={(title) => {
          if (renameTarget) renameCaseLocally(renameTarget.id, title);
          setRenameTarget(null);
        }}
      />
    </section>
  );
}
