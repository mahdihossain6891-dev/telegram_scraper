"use client";

import type { ReactNode } from "react";

type StatCardProps = {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  tone?: "primary" | "danger" | "accent" | "warning" | "success" | "neutral";
  className?: string;
};

export function StatCard({
  label,
  value,
  delta,
  tone = "primary",
  className = "",
}: StatCardProps) {
  return (
    <div className={`stat-card metric-card tone-${tone} ${className}`.trim()}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {delta != null ? <div className="metric-delta">{delta}</div> : null}
    </div>
  );
}
