"""Investigation engine — deterministic analysis before any LLM call."""

from __future__ import annotations

from typing import Any

from ai.investigation.context import InvestigationContext, InvestigationFinding, ToolExecution
from ai.investigation.threat_analysis import run_threat_analysis


def run_investigation_engine(ctx: InvestigationContext) -> InvestigationContext:
    """Populate findings / risk / behavior / timeline from tool results."""
    by_name = {t.name: t for t in ctx.tool_results}

    risk = by_name.get("risk")
    if risk and risk.ok:
        ctx.risk = {
            "risk_score": risk.data.get("risk_score"),
            "risk_level": risk.data.get("risk_level"),
            "factors": list(risk.data.get("factors") or [])[:12],
        }
        ctx.findings.append(
            InvestigationFinding(
                key="risk",
                title="Risk Assessment",
                summary=risk.summary,
                value=ctx.risk,
            )
        )

    behavior = by_name.get("behavior")
    if behavior and behavior.ok:
        ctx.behavior = {
            k: behavior.data.get(k)
            for k in (
                "user_id",
                "behavior_score",
                "behavior_status",
                "trend",
                "first_seen",
                "last_seen",
                "metrics",
            )
            if behavior.data.get(k) is not None
        }
        ctx.alerts = list(behavior.data.get("alerts") or ctx.alerts)
        ctx.findings.append(
            InvestigationFinding(
                key="behavior",
                title="Behavioral Analysis",
                summary=behavior.summary,
                value={
                    "behavior_score": behavior.data.get("behavior_score"),
                    "behavior_status": behavior.data.get("behavior_status"),
                    "trend": behavior.data.get("trend"),
                    "metrics": behavior.data.get("metrics") or {},
                },
            )
        )

    alerts = by_name.get("alerts")
    if alerts and alerts.ok:
        merged = list(alerts.data.get("alerts") or [])
        if merged:
            ctx.alerts = merged
        ctx.findings.append(
            InvestigationFinding(
                key="alerts",
                title="Alerts",
                summary=alerts.summary,
                value={"count": len(ctx.alerts), "alert_id": alerts.data.get("alert_id")},
            )
        )

    timeline = by_name.get("timeline")
    if timeline and timeline.ok:
        ctx.timeline = list(timeline.data.get("events") or [])
        ctx.findings.append(
            InvestigationFinding(
                key="timeline",
                title="Activity Timeline",
                summary=timeline.summary,
                value={
                    "event_count": len(ctx.timeline),
                    "first_seen": timeline.data.get("first_seen"),
                    "last_seen": timeline.data.get("last_seen"),
                },
            )
        )

    rel = by_name.get("relationship")
    if rel and rel.ok:
        ctx.relationships = list(rel.data.get("edges") or [])
        ctx.findings.append(
            InvestigationFinding(
                key="relationships",
                title="Relationships",
                summary=rel.summary,
                value={
                    "edge_count": len(ctx.relationships),
                    "group_count": rel.data.get("group_count"),
                },
            )
        )

    personnel = by_name.get("personnel")
    if personnel and personnel.ok:
        ctx.findings.append(
            InvestigationFinding(
                key="dossier",
                title="Personnel Dossier",
                summary=personnel.summary,
                value={
                    "display_name": personnel.data.get("display_name"),
                    "username": personnel.data.get("username"),
                    "message_count": personnel.data.get("message_count"),
                    "group_count": len(personnel.data.get("groups") or []),
                },
            )
        )

    search = by_name.get("search")
    if search and search.ok:
        evidence = list(search.data.get("evidence") or [])
        citations = list(search.data.get("citations") or [])
        ctx.evidence = evidence
        ctx.citations = citations
        labels = [e.get("label") for e in evidence if e.get("label")]
        ctx.findings.append(
            InvestigationFinding(
                key="evidence",
                title="Supporting Evidence",
                summary=search.summary,
                value={"count": len(evidence)},
                citation_labels=[str(x) for x in labels[:12]],
            )
        )

    dashboard = by_name.get("dashboard")
    if dashboard and dashboard.ok:
        matched = list(dashboard.data.get("matched") or [])
        ctx.findings.append(
            InvestigationFinding(
                key="dashboard",
                title="Dashboard Modules",
                summary=dashboard.summary,
                value={"matched": matched, "hint": dashboard.data.get("hint")},
            )
        )

    report = by_name.get("report")
    if report and report.ok:
        ctx.findings.append(
            InvestigationFinding(
                key="report",
                title="Report Orchestration",
                summary=report.summary,
                value=report.data,
            )
        )

    # Activity trend from behavior metrics when present.
    metrics = (ctx.behavior or {}).get("metrics") or {}
    if metrics:
        trend_bits = []
        if metrics.get("night_activity_ratio") is not None:
            trend_bits.append(f"night_activity_ratio={metrics.get('night_activity_ratio')}")
        if metrics.get("forward_rate") is not None:
            trend_bits.append(f"forward_rate={metrics.get('forward_rate')}")
        if trend_bits:
            ctx.findings.append(
                InvestigationFinding(
                    key="activity_trend",
                    title="Activity Trend Signals",
                    summary="; ".join(trend_bits),
                    value=metrics,
                )
            )

    ctx.threat_report = run_threat_analysis(ctx).to_dict()
    ctx.findings.append(
        InvestigationFinding(
            key="threat_intelligence",
            title="Threat Intelligence Report",
            summary=(
                (ctx.threat_report.get("executive_summary") or "")[:240]
                or "Enterprise threat analysis completed."
            ),
            value={
                "risk_band": (ctx.threat_report.get("risk_scores") or {}).get("risk_band"),
                "final_score": (ctx.threat_report.get("risk_scores") or {}).get("final_score"),
                "activity_assessment": ctx.threat_report.get("activity_assessment"),
                "likely_false_positive": (
                    (ctx.threat_report.get("false_positive_assessment") or {}).get(
                        "likely_false_positive"
                    )
                ),
            },
        )
    )

    return ctx


def tool_executions_from_results(results: list[Any]) -> list[ToolExecution]:
    out: list[ToolExecution] = []
    for r in results:
        out.append(
            ToolExecution(
                name=getattr(r, "name", "tool"),
                ok=bool(getattr(r, "ok", False)),
                summary=str(getattr(r, "summary", "") or ""),
                data=dict(getattr(r, "data", None) or {}),
                error=getattr(r, "error", None),
            )
        )
    return out
