"""Tests for enterprise threat intelligence analysis."""

from __future__ import annotations

from ai.investigation.context import InvestigationContext, ToolExecution
from ai.investigation.engine import run_investigation_engine
from ai.investigation.threat_analysis import (
    format_threat_report_markdown,
    run_threat_analysis,
)


def _reference_evidence_ctx() -> InvestigationContext:
    ctx = InvestigationContext(question="Investigate user", session_id="s1")
    ctx.subject = {
        "user_id": 12345,
        "username": "monitor_bot",
        "display_name": "Keyword Monitor",
    }
    ctx.tool_results = [
        ToolExecution(
            name="risk",
            ok=True,
            summary="Risk score=70 (High)",
            data={
                "risk_score": 70,
                "risk_level": "High",
                "factors": ["keyword:methamphetamine+34"],
            },
        ),
        ToolExecution(
            name="behavior",
            ok=True,
            summary="Behavior score=10",
            data={
                "behavior_score": 10,
                "behavior_status": "Normal",
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": "2024-06-01T00:00:00Z",
                "metrics": {"message_count": 2},
            },
        ),
        ToolExecution(
            name="personnel",
            ok=True,
            summary="Dossier",
            data={
                "user_id": 12345,
                "username": "monitor_bot",
                "display_name": "Keyword Monitor",
                "message_count": 2,
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": "2024-06-01T00:00:00Z",
                "groups": [{"chat_id": 1, "title": "SOC Test"}],
            },
        ),
        ToolExecution(
            name="relationship",
            ok=True,
            summary="1 edge",
            data={"edges": [{"chat_id": 1, "title": "SOC Test", "type": "shared_chat"}]},
        ),
        ToolExecution(
            name="search",
            ok=True,
            summary="Retrieved 1",
            data={
                "evidence": [
                    {
                        "label": "[E1]",
                        "snippet": (
                            "Narcotics keyword dictionary for monitoring: "
                            "methamphetamine, heroin — reference only."
                        ),
                        "timestamp": "2024-05-01T12:00:00Z",
                        "keywords": ["methamphetamine", "heroin"],
                        "group_name": "SOC Test",
                    }
                ],
                "citations": [],
            },
        ),
    ]
    return run_investigation_engine(ctx)


def test_threat_analysis_reference_content_lowers_risk() -> None:
    ctx = _reference_evidence_ctx()
    report = run_threat_analysis(ctx)
    assert report.false_positive_assessment.get("likely_false_positive") is True
    assert report.activity_assessment == "informational"
    assert report.risk_scores["final_score"] <= 50
    assert report.risk_scores["risk_band"] in {"LOW", "MEDIUM"}


def test_threat_report_markdown_has_required_sections() -> None:
    ctx = _reference_evidence_ctx()
    report = run_threat_analysis(ctx)
    md = format_threat_report_markdown(report)
    for heading in (
        "## Executive Summary",
        "## Subject Information",
        "## Risk Assessment",
        "## Evidence Analysis",
        "## False Positive Assessment",
        "## Analyst Recommendation",
    ):
        assert heading in md


def test_engine_attaches_threat_report() -> None:
    ctx = _reference_evidence_ctx()
    assert ctx.threat_report
    assert ctx.threat_report.get("executive_summary")
    assert any(f.key == "threat_intelligence" for f in ctx.findings)


def test_operational_language_raises_intent_score() -> None:
    ctx = InvestigationContext(question="x", session_id="s")
    ctx.evidence = [
        {
            "label": "[E1]",
            "snippet": "Meth for sale, DM me for price and delivery today.",
            "keywords": ["meth"],
        }
    ]
    ctx.risk = {"risk_score": 65}
    report = run_threat_analysis(ctx)
    row = report.evidence_analysis[0]
    assert row["intent_classification"] == "Selling"
    assert report.risk_scores["intent_score"] >= 60
