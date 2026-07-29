"use client";

import type { ReactNode } from "react";

type UserActivityCardProps = {
  name: string;
  userId?: string | number;
  riskLevel?: string;
  riskScore?: number;
  flagged?: number;
  source?: string;
  action?: ReactNode;
};

export function UserActivityCard({
  name,
  userId,
  riskLevel = "Low",
  riskScore,
  flagged,
  source,
  action,
}: UserActivityCardProps) {
  const level = String(riskLevel).toLowerCase();
  return (
    <article className="user-activity-card glass-card">
      <div className="user-activity-main">
        <div className="user-avatar" aria-hidden="true">
          {name.slice(0, 1).toUpperCase()}
        </div>
        <div>
          <strong>{name}</strong>
          {userId != null ? <div className="caption mono">ID {userId}</div> : null}
        </div>
      </div>
      <div className="user-activity-stats">
        <span className={`risk-badge risk-${level}`}>
          {riskLevel}
          {riskScore != null ? ` · ${riskScore}` : ""}
        </span>
        {flagged != null ? <span className="caption">{flagged} flagged</span> : null}
        {source ? <span className="caption truncate">{source}</span> : null}
      </div>
      {action}
    </article>
  );
}
