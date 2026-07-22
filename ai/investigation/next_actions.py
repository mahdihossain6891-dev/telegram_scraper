"""Next-action recommendations derived from investigation context."""

from __future__ import annotations

from ai.investigation.context import InvestigationContext, NextAction


def recommend_next_actions(ctx: InvestigationContext) -> list[NextAction]:
    """Deterministic follow-ups — informed by threat intelligence when available."""
    actions: list[NextAction] = []
    subject = ctx.subject or {}
    label = (
        subject.get("display_name")
        or (f"@{subject['username']}" if subject.get("username") else None)
        or (f"user {subject['user_id']}" if subject.get("user_id") is not None else "this subject")
    )

    threat = dict(ctx.threat_report or {})
    risk = dict(threat.get("risk_scores") or {})
    rec = dict(threat.get("analyst_recommendation") or {})
    band = str(risk.get("risk_band") or "").upper()
    fp = dict(threat.get("false_positive_assessment") or {})

    if rec.get("recommended_action"):
        actions.append(
            NextAction(
                id="threat_recommendation",
                label=f"Priority: {rec.get('priority', 'Medium')}",
                reason=str(rec.get("recommended_action")),
                prompt=f"Continue investigation of {label} per analyst recommendation.",
            )
        )

    if band in {"HIGH", "CRITICAL"} and ctx.relationships:
        actions.append(
            NextAction(
                id="connected_users",
                label="Investigate related accounts",
                reason="Elevated risk with relationship edges — expand network analysis.",
                prompt=f"Find related users connected to {label}",
            )
        )
    elif ctx.relationships:
        actions.append(
            NextAction(
                id="connected_users",
                label="Investigate connected users",
                reason="Relationship edges were found in monitored shared chats.",
                prompt=f"Find related users connected to {label}",
            )
        )

    if ctx.alerts:
        actions.append(
            NextAction(
                id="review_alerts",
                label="Review recent alerts",
                reason=f"{len(ctx.alerts)} alert(s) are attached to this subject.",
                prompt=f"Explain recent alerts for {label}",
            )
        )
    elif band in {"MEDIUM", "HIGH", "CRITICAL"}:
        actions.append(
            NextAction(
                id="analyze_behavior",
                label="Analyze behavior",
                reason="Elevated risk warrants deeper behavioral review.",
                prompt=f"Analyze behavioral anomalies for {label}",
            )
        )
    else:
        actions.append(
            NextAction(
                id="analyze_behavior",
                label="Analyze behavior",
                reason="Behavioral analytics can surface anomalies not visible in messages alone.",
                prompt=f"Analyze behavioral anomalies for {label}",
            )
        )

    if ctx.timeline:
        actions.append(
            NextAction(
                id="review_timeline",
                label="Review timeline",
                reason="A chronological activity trail is available.",
                prompt=f"Generate a timeline for {label}",
            )
        )

    if fp.get("likely_false_positive"):
        actions.append(
            NextAction(
                id="validate_keywords",
                label="Validate keyword context",
                reason="False positive indicators detected — confirm reference vs operational content.",
                prompt=f"Review keyword context for {label} and confirm intent classification.",
            )
        )

    if ctx.relationships and band != "LOW":
        actions.append(
            NextAction(
                id="open_graph",
                label="Open relationship graph",
                reason="Use the Relationship Graph module for interactive exploration.",
                prompt=f"Open relationship graph for {label}",
            )
        )

    actions.append(
        NextAction(
            id="generate_report",
            label="Generate report",
            reason="Structured findings can be exported as an intelligence report.",
            prompt=f"Generate an investigation report for {label}",
        )
    )

    seen: set[str] = set()
    out: list[NextAction] = []
    for a in actions:
        if a.id in seen:
            continue
        seen.add(a.id)
        out.append(a)
        if len(out) >= 5:
            break
    return out
