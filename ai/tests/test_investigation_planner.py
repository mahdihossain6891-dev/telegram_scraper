"""Tests for Phase 5 Investigation Planner."""

from __future__ import annotations

from pathlib import Path

from ai.config import AISettings, clear_ai_settings_cache
from ai.investigation.context import InvestigationContext
from ai.investigation.context_builder import InvestigationContextBuilder
from ai.investigation.evidence_validation import validate_investigation_evidence
from ai.investigation.intents import classify_intent
from ai.investigation.planner import InvestigationPlanner, PlanExecutor
from ai.investigation.tools.base import ToolRegistry, ToolResult


def _settings(**overrides) -> AISettings:
    base = dict(
        enabled=True,
        chat_provider="ollama",
        chat_model="test",
        embedding_provider="ollama",
        embedding_model="test",
        api_base_url="http://127.0.0.1:11434",
        api_key="",
        vector_backend="none",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.1,
        max_tokens=256,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=Path("."),
        embed_batch_size=8,
        chunk_max_chars=500,
        chunk_overlap_chars=50,
        index_message_batch_size=10,
        rag_top_k=4,
        rag_max_evidence_items=4,
        rag_max_context_chars=4000,
        rag_context_token_budget=1000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=10,
        assistant_name="Sébastien",
        assistant_history_turns=4,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
        model_cache_ttl_seconds=60.0,
    )
    base.update(overrides)
    return AISettings(**base)  # type: ignore[arg-type]


class _StubTool:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail

    def run(self, *, ctx, **kwargs):
        if self.fail:
            return ToolResult(name=self.name, ok=False, error="boom", summary="failed")
        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"{self.name} ok",
            data={"confidence": 0.9, "freshness": 0.8, "completeness": 0.7},
        )


def test_planner_emits_structured_plan() -> None:
    intent = classify_intent("Investigate user @alice for high risk")
    plan = InvestigationPlanner().plan(
        intent,
        question="Investigate user @alice for high risk",
        target={"user_id": 1, "username": "alice"},
        available_tools=["risk", "behavior", "alerts", "personnel", "timeline", "relationship", "search"],
    )
    assert plan.intent_key == "investigate_user"
    assert "risk" in plan.required_tools or "risk" in [s.tool for s in plan.steps]
    assert plan.to_dict()["plan_id"]
    assert plan.evidence_needed


def test_plan_preview_includes_estimates() -> None:
    intent = classify_intent("Analyze behavior for this user")
    preview = InvestigationPlanner().preview(
        intent,
        question="Analyze behavior for this user",
        available_tools=["behavior", "alerts", "risk", "timeline", "search"],
    )
    assert preview["intent"] == "analyze_behavior"
    assert preview["estimated_execution_ms"] > 0
    assert "optional_tools" in preview


def test_executor_continues_on_tool_failure() -> None:
    registry = ToolRegistry()
    registry.register(_StubTool("risk"))
    registry.register(_StubTool("behavior", fail=True))
    registry.register(_StubTool("search"))
    intent = classify_intent("Investigate user risk")
    plan = InvestigationPlanner().plan(
        intent,
        question="Investigate user risk",
        target={"user_id": 9},
        available_tools=["risk", "behavior", "search"],
    )
    ctx = InvestigationContext(question="Investigate user risk", session_id="s1")
    ctx.subject = {"user_id": 9}
    executions, records = PlanExecutor(registry).execute(
        plan, ctx=ctx, retrieval_question="Investigate user risk", use_cache=False
    )
    assert executions
    assert any(not r.ok for r in records)
    assert any(r.ok for r in records)


def test_context_builder_dedupes_and_ranks() -> None:
    ctx = InvestigationContext(question="q", session_id="s")
    ctx.evidence = [
        {"label": "[E1]", "source_id": "1", "snippet": "a", "confidence": 0.4},
        {"label": "[E1]", "source_id": "1", "snippet": "a", "confidence": 0.4},
        {"label": "[E2]", "source_id": "2", "snippet": "b", "timestamp": "2024-01-01", "confidence": 0.9},
    ]
    built = InvestigationContextBuilder().build(ctx)
    assert built["evidence_count"] == 2
    assert built["package"]["evidence"][0]["label"] == "[E2]"


def test_evidence_validation_assigns_confidence() -> None:
    ctx = InvestigationContext(question="q", session_id="s")
    ctx.evidence = [
        {"label": "[E1]", "source_id": "1", "snippet": "hello"},
        {"label": "[E1]", "source_id": "1", "snippet": "hello"},
    ]
    report = validate_investigation_evidence(ctx)
    assert report["evidence_count"] == 1
    assert ctx.evidence[0].get("confidence") is not None


def test_new_intents_register() -> None:
    assert classify_intent("keyword analysis for wallet").key == "keyword_analysis"
    assert classify_intent("risk assessment for this user").key == "risk_assessment"
    assert classify_intent("find similar users").key == "find_similar_users"
    assert classify_intent("search conversations about ransom").key == "search_conversations"


def teardown_module(_module) -> None:
    clear_ai_settings_cache()
