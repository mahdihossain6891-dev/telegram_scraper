"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  onOpen: () => void;
  onRename: () => void;
  onDismiss: () => void;
};

export function CaseContextMenu({ onOpen, onRename, onDismiss }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ai-case-menu" ref={rootRef}>
      <button
        type="button"
        className="ai-case-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Case actions"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      {open ? (
        <ul className="ai-case-menu-list" role="menu">
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                onOpen();
              }}
            >
              Open
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                onRename();
              }}
            >
              Rename
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              className="danger"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                onDismiss();
              }}
            >
              Dismiss Case
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
