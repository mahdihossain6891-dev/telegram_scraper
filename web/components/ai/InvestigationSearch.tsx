"use client";

import { FormEvent, forwardRef, useImperativeHandle, useRef } from "react";

import type { EntityKind } from "./types";
import { ENTITY_OPTIONS } from "./types";
import { IconSearch, IconSend } from "./icons";

export type InvestigationSearchHandle = {
  focus: () => void;
};

type Props = {
  query: string;
  onQueryChange: (value: string) => void;
  placeholder?: string;
  actionLabel?: string | null;
  onClearAction?: () => void;
  entityKind: EntityKind | null;
  onEntityKindChange: (kind: EntityKind | null) => void;
  entityValue: string;
  onEntityValueChange: (value: string) => void;
  busy: boolean;
  onSubmit: (event?: FormEvent) => void;
};

export const InvestigationSearch = forwardRef<InvestigationSearchHandle, Props>(
  function InvestigationSearch(
    {
      query,
      onQueryChange,
      placeholder,
      actionLabel,
      onClearAction,
      entityKind,
      onEntityKindChange,
      entityValue,
      onEntityValueChange,
      busy,
      onSubmit,
    },
    ref,
  ) {
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      focus: () => {
        inputRef.current?.focus();
        inputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      },
    }));

    return (
      <form className="ai-search-block" onSubmit={(e) => void onSubmit(e)}>
        {actionLabel ? (
          <div className="ai-action-chip-row">
            <span className="ai-action-chip">
              {actionLabel}
              {onClearAction ? (
                <button
                  type="button"
                  className="ai-action-chip-clear"
                  aria-label="Clear investigation type"
                  onClick={onClearAction}
                >
                  ×
                </button>
              ) : null}
            </span>
          </div>
        ) : null}

        <div className="ai-search-main">
          <span className="ai-search-icon" aria-hidden="true">
            <IconSearch />
          </span>
          <label className="sr-only" htmlFor="ai-investigate-query">
            Investigation query
          </label>
          <textarea
            ref={inputRef}
            id="ai-investigate-query"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            rows={2}
            placeholder={
              placeholder ||
              "Investigate a user, group, message, wallet, phone number, or suspicious activity..."
            }
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void onSubmit();
              }
            }}
            disabled={busy}
          />
          <button
            type="submit"
            className="btn primary ai-send"
            disabled={busy || !query.trim()}
          >
            <IconSend />
            <span>{busy ? "Working…" : "Investigate"}</span>
          </button>
        </div>

        <div className="ai-entity-row" role="group" aria-label="Entity focus">
          {ENTITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={
                entityKind === opt.value ? "ai-entity-chip active" : "ai-entity-chip"
              }
              onClick={() =>
                onEntityKindChange(entityKind === opt.value ? null : opt.value)
              }
            >
              {opt.label}
            </button>
          ))}
        </div>

        {entityKind ? (
          <div className="ai-entity-input">
            <label htmlFor="ai-entity-value">
              Focus · {ENTITY_OPTIONS.find((o) => o.value === entityKind)?.label}
            </label>
            <input
              id="ai-entity-value"
              value={entityValue}
              onChange={(e) => onEntityValueChange(e.target.value)}
              placeholder={
                entityKind === "username"
                  ? "@username or numeric ID"
                  : entityKind === "wallet"
                    ? "Wallet address"
                    : entityKind === "phone"
                      ? "Phone number"
                      : `Enter ${entityKind}…`
              }
              disabled={busy}
            />
            <button
              type="button"
              className="btn ai-btn-ghost"
              onClick={() => {
                onEntityKindChange(null);
                onEntityValueChange("");
              }}
            >
              Clear
            </button>
          </div>
        ) : null}
      </form>
    );
  },
);
