import type { AiRetrieved } from "@/components/ai/types";

export type ThreatReport = {
  executive_summary?: string;
  activity_assessment?: string;
  detection_reason?: string;
  subject_overview?: Record<string, unknown>;
  risk_scores?: {
    detection_score?: number;
    behavior_score?: number;
    network_score?: number;
    intent_score?: number;
    false_positive_adjustment?: number;
    final_score?: number;
    risk_band?: string;
    risk_level?: string;
    explanation?: string;
  };
  threat_categories?: Array<{
    category?: string;
    detection?: string;
    threat_type?: string;
    intent?: string;
    confidence_pct?: number;
    evidence?: string;
  }>;
  confidence_level?: {
    score_pct?: number;
    label?: string;
    reason?: string;
  };
  evidence_analysis?: Array<{
    label?: string;
    message?: string;
    timestamp?: string;
    chat?: string;
    sender?: string;
    intent_classification?: string;
    intent_confidence_pct?: number;
    intent_reason?: string;
  }>;
  network_analysis?: {
    edge_count?: number;
    group_count?: number;
    suspicious_edges?: number;
    summary?: string;
    edges?: Array<Record<string, unknown>>;
  };
  behavioral_analysis?: {
    behavior_score?: number;
    behavior_status?: string;
    summary?: string;
    findings?: string[];
  };
  false_positive_assessment?: {
    likely_false_positive?: boolean;
    summary?: string;
  };
  analyst_recommendation?: {
    priority?: string;
    recommended_action?: string;
    escalation_triggers?: string[];
  };
};

export function parseThreatReport(value: unknown): ThreatReport | null {
  if (!value || typeof value !== "object") return null;
  return value as ThreatReport;
}

export function primaryThreatCategory(report: ThreatReport | null): string {
  const cat = report?.threat_categories?.[0];
  if (!cat) return "—";
  return cat.category || cat.detection || "—";
}

export function evidenceCount(
  report: ThreatReport | null,
  retrieved?: AiRetrieved[],
): number {
  if (report?.evidence_analysis?.length) return report.evidence_analysis.length;
  return retrieved?.length || 0;
}
