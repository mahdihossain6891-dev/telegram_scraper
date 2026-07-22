"use client";

import { useEffect, useId, useRef, useState } from "react";

type Props = {
  open: boolean;
  caseTitle: string;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DismissCaseDialog({ open, caseTitle, onCancel, onConfirm }: Props) {
  const titleId = useId();
  const descId = useId();
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="ai-dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="ai-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId}>Dismiss Investigation?</h2>
        <p id={descId}>
          This will remove the investigation from your active workspace and history. This
          action will not delete any underlying intelligence, messages, alerts, behavioral
          data, or evidence.
        </p>
        {caseTitle ? (
          <p className="caption ai-dialog-case">Case: {caseTitle}</p>
        ) : null}
        <div className="ai-dialog-actions">
          <button type="button" className="btn ai-btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="btn ai-btn-danger"
            onClick={onConfirm}
          >
            Dismiss Case
          </button>
        </div>
      </div>
    </div>
  );
}

type RenameProps = {
  open: boolean;
  initialTitle: string;
  onCancel: () => void;
  onConfirm: (title: string) => void;
};

export function RenameCaseDialog({ open, initialTitle, onCancel, onConfirm }: RenameProps) {
  const titleId = useId();
  const [value, setValue] = useState(initialTitle);

  useEffect(() => {
    if (open) setValue(initialTitle);
  }, [open, initialTitle]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="ai-dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="ai-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId}>Rename Investigation</h2>
        <label className="ai-dialog-field">
          Case name
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onConfirm(value);
              }
            }}
          />
        </label>
        <div className="ai-dialog-actions">
          <button type="button" className="btn ai-btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn primary ai-send"
            disabled={!value.trim()}
            onClick={() => onConfirm(value)}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
