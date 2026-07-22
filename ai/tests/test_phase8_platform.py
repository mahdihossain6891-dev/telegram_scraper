"""Phase 8 platform tests — no LLM / Mongo required."""

from __future__ import annotations

import pytest

from ai.agents.registry import AgentRegistry
from ai.cache.semantic import SemanticCache
from ai.core.structured_response import StructuredResponse
from ai.core.types import PlatformEnvironment
from ai.evidence.engine import EvidenceEngine
from ai.evidence.models import Evidence
from ai.investigation.context import InvestigationContext, InvestigationFinding, ToolExecution
from ai.investigation.intents import classify_intent
from ai.investigation.tools import build_investigation_tools
from ai.memory.manager import EnvironmentIsolationError, MemoryManager
from ai.reasoning.engine import ReasoningEngine
from ai.security.policy import EnvironmentGuard, ReadOnlyPolicy, ReadOnlyViolation
from ai.tools.registry import CapabilityRegistry
from ai.tools.router import ToolRouter


def test_capability_registry_discovers_tools() -> None:
    tools = build_investigation_tools()
    registry = CapabilityRegistry.from_investigation_tools(tools)
    caps = registry.list_capabilities()
    names = {c.name for c in caps}
    assert "behavior" in names
    assert "search" in names
    assert registry.get_tool("risk") is not None


def test_tool_router_uses_intent_plan() -> None:
    tools = build_investigation_tools()
    registry = CapabilityRegistry.from_investigation_tools(tools)
    router = ToolRouter(registry)
    intent = classify_intent("Analyze behavioral anomalies for this user")
    routed = router.route(intent)
    assert "behavior" in routed


def test_tool_router_discovers_without_orchestrator_edit() -> None:
    registry = CapabilityRegistry()
    tools = build_investigation_tools()
    for name in tools.list_tools():
        tool = tools.get(name)
        if tool:
            registry.register(tool)
    router = ToolRouter(registry)
    intent = classify_intent("Investigate user risk profile")
    routed = router.route(intent)
    assert routed


def test_evidence_engine_collects_and_ranks() -> None:
    ctx = InvestigationContext(question="q", session_id="s")
    ctx.evidence = [
        {"label": "[E1]", "snippet": "urgent transfer", "score": 0.9, "source_type": "message"},
        {"label": "[E1]", "snippet": "urgent transfer", "score": 0.9, "source_type": "message"},
        {"label": "[E2]", "snippet": "hello", "score": 0.2, "source_type": "message"},
    ]
    ctx.risk = {"risk_score": 80, "risk_level": "High"}
    engine = EvidenceEngine()
    items = engine.collect(ctx)
    assert len(items) >= 2
    assert items[0].confidence >= items[-1].confidence


def test_evidence_model_from_retrieved() -> None:
    ev = Evidence.from_retrieved(
        {"label": "[E1]", "snippet": "test", "score": 0.8, "source_id": "42"},
        environment="live",
    )
    assert ev.environment == "live"
    assert ev.citation == "[E1]"


def test_reasoning_engine_detects_gaps() -> None:
    ctx = InvestigationContext(question="q", session_id="s")
    ctx.subject = {"user_id": 1}
    engine = ReasoningEngine()
    package = engine.prepare(ctx)
    assert package["gaps"]


def test_memory_environment_isolation() -> None:
    memory = MemoryManager()
    live = PlatformEnvironment.LIVE
    sim = PlatformEnvironment.SIMULATION
    memory.put(kind="session", key="s1", value={"a": 1}, environment=live)
    memory.put(kind="session", key="s1", value={"b": 2}, environment=sim)
    assert memory.get(kind="session", key="s1", environment=live) == {"a": 1}
    assert memory.get(kind="session", key="s1", environment=sim) == {"b": 2}
    with pytest.raises(EnvironmentIsolationError):
        memory.assert_environment_match(live, "simulation")


def test_environment_guard_merges_filters() -> None:
    env = EnvironmentGuard.resolve({"environment": "simulation"})
    assert env == PlatformEnvironment.SIMULATION
    merged = EnvironmentGuard.merge_filters({"user_id": 1}, env)
    assert merged["environment"] == "simulation"


def test_read_only_policy_blocks_writes() -> None:
    with pytest.raises(ReadOnlyViolation):
        ReadOnlyPolicy.validate_tool_name("delete_evidence")


def test_semantic_cache_hit_miss() -> None:
    cache = SemanticCache()
    key = cache.make_key("question", "session")
    cache.set(key, {"answer": "x"})
    assert cache.get(key) == {"answer": "x"}
    stats = cache.stats()
    assert stats["hits"] >= 1
    cache.invalidate(key=key)
    assert cache.get(key) is None


def test_structured_response_from_context() -> None:
    ctx = InvestigationContext(question="q", session_id="s")
    ctx.intent_key = "investigate_user"
    ctx.answer = "Summary"
    ctx.evidence = [{"label": "[E1]"}]
    ctx.findings = [
        InvestigationFinding(key="risk", title="Risk", summary="High"),
    ]
    structured = StructuredResponse.from_investigation_context(ctx)
    data = structured.to_dict()
    assert data["executive_summary"] == "Summary"
    assert data["evidence"]


def test_agent_registry_lists_future_agents() -> None:
    registry = AgentRegistry()
    agents = registry.list_agents()
    assert len(agents) >= 6
    assert registry.list_enabled() == []


def test_new_tool_registers_without_orchestrator_change() -> None:
    registry = CapabilityRegistry.from_investigation_tools(build_investigation_tools())

    class DemoTool:
        name = "demo_future_tool"

        def run(self, *, ctx, **kwargs):
            from ai.investigation.tools.base import ToolResult

            return ToolResult(name=self.name, ok=True, summary="demo")

    from ai.tools.capabilities import ToolCapability

    registry.register(
        DemoTool(),
        ToolCapability(
            name="demo_future_tool",
            description="Future capability",
            intents=("investigate_user",),
        ),
    )
    router = ToolRouter(registry)
    intent = classify_intent("Investigate user 123")
    routed = router.route(intent)
    assert "demo_future_tool" in routed
