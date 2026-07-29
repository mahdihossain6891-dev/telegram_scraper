"use client";

import { StatCard } from "@/components/ui/StatCard";
import {
  evidenceCount,
  primaryThreatCategory,
  type ThreatReport,
} from "@/components/ai/threat-report";
import type { AiRetrieved } from "@/components/ai/types";
import { riskBandClass, riskBandFromScore } from "@/lib/risk-bands";

type Focus = "risk" | "behavior" | "alerts" | "network" | "report" | "general";

type Props = {
  report: ThreatReport | null;
  retrieved?: AiRetrieved[];
  confidence?: string;
  /** Emphasize metrics relevant to the active investigation type. */
  focus?: Focus;
};

function toneForBand(band: string): "success" | "warning" | "accent" | "danger" | "neutral" {
  const b = band.toUpperCase();
  if (b === "LOW") return "success";
  if (b === "MEDIUM") return "warning";
  if (b === "HIGH") return "accent";
  if (b === "CRITICAL") return "danger";
  return "neutral";
}

const FOCUS_LABELS: Record<Focus, string[]> = {
  risk: ["Risk Score", "Threat Category", "Confidence", "Evidence Count"],
  behavior: ["Behavior Score", "Risk Score", "Confidence", "Evidence Count"],
  alerts: ["Risk Score", "Threat Category", "Evidence Count", "Confidence"],
  network: ["Network Score", "Risk Score", "Evidence Count", "Confidence"],
  report: ["Risk Score", "Threat Category", "Confidence", "Evidence Count"],
  general: [
    "Risk Score",
    "Threat Category",
    "Confidence",
    "Evidence Count",
    "Behavior Score",
    "Network Score",
  ],
};

export function InvestigationMetricsGrid({
  report,
  retrieved,
  confidence,
  focus = "general",
}: Props) {
  const risk = report?.risk_scores;
  const band = risk?.risk_band || riskBandFromScore(risk?.final_score);
  const confPct = report?.confidence_level?.score_pct;
  const confLabel =
    report?.confidence_level?.label || confidence || "—";

  const allCards = [
    {
      label: "Risk Score",
      value: risk?.final_score ?? "—",
      sub: band,
      tone: toneForBand(String(band)),
      bandClass: riskBandClass(band),
    },
    {
      label: "Threat Category",
      value: primaryThreatCategory(report),
      sub: report?.threat_categories?.[0]?.intent || "Intent unknown",
      tone: "neutral" as const,
    },
    {
      label: "Confidence",
      value: confPct != null ? `${confPct}%` : confLabel,
      sub: report?.confidence_level?.reason?.slice(0, 48) || "Assessment confidence",
      tone: "primary" as const,
    },
    {
      label: "Evidence Count",
      value: evidenceCount(report, retrieved),
      sub: "Flagged items analyzed",
      tone: "primary" as const,
    },
    {
      label: "Behavior Score",
      value:
        risk?.behavior_score ??
        report?.behavioral_analysis?.behavior_score ??
        "—",
      sub: report?.behavioral_analysis?.behavior_status || "Behavioral posture",
      tone: "neutral" as const,
    },
    {
      label: "Network Score",
      value: risk?.network_score ?? report?.network_analysis?.edge_count ?? "—",
      sub:
        report?.network_analysis?.summary?.slice(0, 56) ||
        `${report?.network_analysis?.edge_count ?? 0} edges`,
      tone: "neutral" as const,
    },
  ];

  const allow = new Set(FOCUS_LABELS[focus] || FOCUS_LABELS.general);
  const cards = allCards.filter((card) => allow.has(card.label));

  return (
    <section
      className="investigation-metrics-grid"
      aria-label={`${focus} investigation metrics`}
    >      {cards.map((card) => (
        <StatCard
          key={card.label}
          label={card.label}
          value={
            card.bandClass ? (
              <span className={card.bandClass}>
                {card.value}
                {card.sub ? (
                  <span className="investigation-metric-sub"> {String(card.sub)}</span>
                ) : null}
              </span>
            ) : (
              card.value
            )
          }
          delta={card.bandClass ? undefined : card.sub}
          tone={card.tone}
          className="investigation-metric-card"
        />
      ))}
    </section>
  );
}
