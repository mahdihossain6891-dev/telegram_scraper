/** SOC risk band colors — LOW green, MEDIUM yellow, HIGH orange, CRITICAL red. */

export type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;

export function normalizeRiskBand(value: string | null | undefined): RiskBand {
  const v = (value || "").toUpperCase().trim();
  if (v === "LOW" || v === "MEDIUM" || v === "HIGH" || v === "CRITICAL") return v;
  if (v === "NORMAL" || v === "INFORMATIONAL") return "LOW";
  if (v === "SUSPICIOUS" || v === "UNUSUAL") return "MEDIUM";
  return v || "LOW";
}

export function riskBandClass(band: string | null | undefined): string {
  switch (normalizeRiskBand(band)) {
    case "LOW":
      return "risk-band risk-band-low";
    case "MEDIUM":
      return "risk-band risk-band-medium";
    case "HIGH":
      return "risk-band risk-band-high";
    case "CRITICAL":
      return "risk-band risk-band-critical";
    default:
      return "risk-band risk-band-unknown";
  }
}

export function riskBandFromScore(score: number | null | undefined): RiskBand {
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  if (s <= 20) return "LOW";
  if (s <= 50) return "MEDIUM";
  if (s <= 75) return "HIGH";
  return "CRITICAL";
}

export function riskBandLabel(band: string | null | undefined): string {
  return normalizeRiskBand(band);
}
