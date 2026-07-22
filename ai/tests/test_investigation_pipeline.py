"""Tests for Sébastien investigation pipeline (no LLM / no Mongo required)."""

from __future__ import annotations

from ai.investigation.confidence import assess_confidence
from ai.investigation.context import InvestigationContext, ToolExecution
from ai.investigation.engine import run_investigation_engine
from ai.investigation.intents import classify_intent
from ai.investigation.next_actions import recommend_next_actions
from ai.investigation.validators import validate_intent_inputs


def test_classify_investigate_user() -> None:
    intent = classify_intent("Investigate Ratul and summarize risk")
    assert intent.key == "investigate_user"


def test_classify_bare_lowercase_name() -> None:
    intent = classify_intent("adib malay")
    assert intent.key == "investigate_user"
    assert intent.block_llm is False


def test_extract_bare_lowercase_name() -> None:
    from ai.investigation.entity_resolution import extract_entity_mentions

    mentions = extract_entity_mentions("adib malay")
    assert len(mentions) >= 1
    assert mentions[0].raw.lower() == "adib malay"


def test_classify_bare_username() -> None:
    intent = classify_intent("@adib_malay")
    assert intent.key == "investigate_user"


def test_classify_analyze_behavior() -> None:
    intent = classify_intent("Analyze behavioral anomalies for this user")
    assert intent.key == "analyze_behavior"
    assert "behavior" in intent.tools


def test_classify_unknown_blocks_llm() -> None:
    intent = classify_intent("tell me a joke about cats")
    assert intent.key == "unknown"
    assert intent.block_llm is True


def test_suggested_prompts_are_not_entity_mentions() -> None:
    from ai.investigation.entity_resolution import extract_entity_mentions

    for q in (
        "Why is this user high risk?",
        "Show behavioral anomalies",
        "Dashboard summary",
        "Fleet overview",
        "Generate investigation summary",
    ):
        assert extract_entity_mentions(q) == [], q


def test_classify_prompt_phrases_not_bare_entity() -> None:
    assert classify_intent("Why is this user high risk?").key == "investigate_user"
    assert classify_intent("Dashboard summary").key == "dashboard_summary"
    assert classify_intent("adib malay").key == "investigate_user"


def test_validate_requires_user() -> None:
    intent = classify_intent("Investigate this user")
    result = validate_intent_inputs(
        intent,
        question="Investigate this user",
        subject={},
        entity_status="not_required",
    )
    assert result.ok is False
    assert "user" in result.missing


def test_validate_ok_with_user() -> None:
    intent = classify_intent("Investigate user 12345")
    result = validate_intent_inputs(
        intent,
        question="Investigate user 12345",
        subject={"user_id": 12345},
        entity_status="resolved",
    )
    assert result.ok is True


def test_engine_and_confidence_from_tools() -> None:
    ctx = InvestigationContext(question="Investigate 1", session_id="s1")
    ctx.subject = {"user_id": 1, "display_name": "Ratul"}
    ctx.tool_results = [
        ToolExecution(
            name="risk",
            ok=True,
            summary="Risk score=80 (High)",
            data={"risk_score": 80, "risk_level": "High", "factors": ["keyword:bomb"]},
        ),
        ToolExecution(
            name="behavior",
            ok=True,
            summary="Behavior score=70",
            data={
                "behavior_score": 70,
                "behavior_status": "elevated",
                "alerts": [{"type": "night_spike"}],
                "metrics": {"night_activity_ratio": 0.6},
            },
        ),
        ToolExecution(
            name="search",
            ok=True,
            summary="Retrieved 3",
            data={
                "evidence": [
                    {"label": "[E1]", "snippet": "a", "timestamp": "2024-01-01"},
                    {"label": "[E2]", "snippet": "b", "timestamp": "2024-01-02"},
                    {"label": "[E3]", "snippet": "c", "timestamp": "2024-01-03"},
                ],
                "citations": [
                    {"source_type": "message", "source_id": "1", "label": "[E1]", "snippet": "a"},
                    {"source_type": "message", "source_id": "2", "label": "[E2]", "snippet": "b"},
                    {"source_type": "message", "source_id": "3", "label": "[E3]", "snippet": "c"},
                ],
            },
        ),
    ]
    ctx = run_investigation_engine(ctx)
    assert any(f.key == "risk" for f in ctx.findings)
    assert len(ctx.evidence) == 3
    assert len(ctx.alerts) == 1
    conf = assess_confidence(ctx)
    assert conf.score >= 45
    assert conf.reason
    actions = recommend_next_actions(ctx)
    assert actions
    assert any(a.id == "generate_report" for a in actions)


def test_confidence_low_without_signals() -> None:
    ctx = InvestigationContext(question="x", session_id="s")
    conf = assess_confidence(ctx)
    assert conf.label == "low"
    assert conf.score < 45
