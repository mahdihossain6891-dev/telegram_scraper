"""Evidence-derived confidence — never guessed by the LLM."""

from __future__ import annotations

from ai.investigation.context import ConfidenceAssessment, InvestigationContext


def assess_confidence(ctx: InvestigationContext) -> ConfidenceAssessment:
    """Derive 0–100 confidence from measurable investigation signals."""
    evidence_n = len(ctx.evidence)
    alert_n = len(ctx.alerts)
    rel_n = len(ctx.relationships)
    timeline_n = len(ctx.timeline)
    findings_n = len(ctx.findings)

    risk_score = ctx.risk.get("risk_score") if ctx.risk else None
    behavior_score = ctx.behavior.get("behavior_score") if ctx.behavior else None

    score = 15  # baseline when a validated target exists
    factors: dict[str, object] = {
        "evidence_items": evidence_n,
        "alerts": alert_n,
        "relationships": rel_n,
        "timeline_events": timeline_n,
        "findings": findings_n,
    }

    # Evidence quantity
    if evidence_n >= 10:
        score += 30
    elif evidence_n >= 5:
        score += 22
    elif evidence_n >= 2:
        score += 14
    elif evidence_n == 1:
        score += 6

    # Alerts
    if alert_n >= 3:
        score += 12
    elif alert_n >= 1:
        score += 7

    # Relationships
    if rel_n >= 5:
        score += 10
    elif rel_n >= 1:
        score += 5

    # Timeline depth
    if timeline_n >= 10:
        score += 10
    elif timeline_n >= 3:
        score += 6

    # Risk / behavior agreement
    if risk_score is not None:
        score += 6
        factors["risk_score"] = risk_score
    if behavior_score is not None:
        score += 6
        factors["behavior_score"] = behavior_score
    if risk_score is not None and behavior_score is not None:
        # Agreement bonus when both elevated or both low.
        try:
            rs = int(risk_score)
            bs = int(behavior_score)
            if (rs >= 60 and bs >= 60) or (rs < 40 and bs < 40):
                score += 8
                factors["risk_behavior_agreement"] = True
        except (TypeError, ValueError):
            pass

    # Successful tools
    ok_tools = sum(1 for t in ctx.tool_results if t.ok)
    score += min(10, ok_tools * 2)
    factors["successful_tools"] = ok_tools

    score = max(0, min(100, int(score)))
    if score >= 75:
        label = "high"
    elif score >= 45:
        label = "medium"
    else:
        label = "low"

    bits = []
    if evidence_n:
        bits.append(f"{evidence_n} evidence item(s)")
    if alert_n:
        bits.append(f"{alert_n} alert(s)")
    if timeline_n:
        bits.append(f"{timeline_n} timeline event(s)")
    if rel_n:
        bits.append(f"{rel_n} relationship edge(s)")
    if risk_score is not None:
        bits.append(f"risk_score={risk_score}")
    if behavior_score is not None:
        bits.append(f"behavior_score={behavior_score}")
    if not bits:
        bits.append("limited structured signals after tool execution")

    reason = "Based on " + ", ".join(bits) + "."
    return ConfidenceAssessment(
        score=score,
        label=label,  # type: ignore[arg-type]
        reason=reason,
        factors=factors,
    )
