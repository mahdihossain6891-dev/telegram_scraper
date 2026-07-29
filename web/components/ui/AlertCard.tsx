"use client";

import type { ReactNode } from "react";

type AlertCardProps = {
  title: string;
  severity?: string;
  meta?: ReactNode;
  children?: ReactNode;
  onClick?: () => void;
};

export function AlertCard({ title, severity = "Medium", meta, children, onClick }: AlertCardProps) {
  const level = String(severity).toLowerCase();
  return (
    <article
      className={`alert-card glass-card risk-${level}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") onClick();
            }
          : undefined
      }
    >
      <div className="alert-card-head">
        <span className={`risk-badge risk-${level}`}>{severity}</span>
        <h3 className="alert-card-title">{title}</h3>
      </div>
      {meta ? <div className="alert-card-meta caption">{meta}</div> : null}
      {children ? <div className="alert-card-body">{children}</div> : null}
    </article>
  );
}
