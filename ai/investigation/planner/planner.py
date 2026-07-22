"""InvestigationPlanner — decides WHAT to retrieve and HOW (tool order).

The LLM never selects tools. The planner emits a structured ExecutionPlan;
the Tool Registry executes it.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ai.investigation.intents import InvestigationIntent, tools_for_intent
from ai.investigation.planner.models import ExecutionPlan, PlanStep
from ai.tools.capabilities import BUILTIN_CAPABILITIES
from ai.tools.registry import CapabilityRegistry

_EVIDENCE_BY_TOOL: dict[str, list[str]] = {
    "risk": ["risk_score", "risk_factors"],
    "behavior": ["behavior_profile", "anomalies"],
    "alerts": ["alerts", "alert_triggers"],
    "personnel": ["personnel_dossier", "activity_summary"],
    "timeline": ["timeline_events"],
    "relationship": ["relationship_edges", "shared_groups"],
    "search": ["message_evidence", "citations"],
    "report": ["report_scaffold"],
    "dashboard": ["dashboard_modules"],
    "resolve_entity": ["resolved_subject"],
}

_OPTIONAL_BY_INTENT: dict[str, tuple[str, ...]] = {
    "investigate_user": ("relationship", "timeline"),
    "analyze_behavior": ("timeline",),
    "relationship_analysis": ("timeline",),
    "generate_report": ("timeline", "alerts"),
    "explain_alert": ("timeline",),
    "compare_two_users": ("timeline",),
}

_EXPECTED_OUTPUT: dict[str, str] = {
    "investigate_user": "Risk, behavior, alerts, timeline, and cited evidence for the target user.",
    "investigate_group": "Group activity, risk indicators, and cited messages.",
    "investigate_channel": "Channel activity, risk indicators, and cited messages.",
    "relationship_analysis": "Relationship graph edges and shared-context evidence.",
    "analyze_behavior": "Behavioral anomalies with supporting alerts and evidence.",
    "generate_timeline": "Chronological timeline of monitored activity.",
    "keyword_analysis": "Keyword/message hits with citations.",
    "risk_assessment": "Risk score breakdown with contributing factors.",
    "generate_report": "Structured investigation report scaffold with citations.",
    "summarize_case": "Case summary grounded in findings and evidence.",
    "compare_two_users": "Side-by-side risk/behavior comparison.",
    "search_conversations": "Semantic search hits over monitored conversations.",
    "explain_alert": "Alert explanation with triggers and supporting evidence.",
    "find_similar_users": "Users with similar activity/relationship patterns.",
    "semantic_search": "Semantic search results with citations.",
    "summary": "Investigation summary with key findings.",
    "dashboard_summary": "Fleet/dashboard overview from structured modules.",
    "open_dashboard_page": "Dashboard module navigation links.",
}

_EST_MS: dict[str, int] = {
    "search": 400,
    "relationship": 250,
    "timeline": 200,
    "behavior": 150,
    "risk": 100,
    "alerts": 120,
    "personnel": 120,
    "report": 80,
    "dashboard": 50,
    "resolve_entity": 80,
}


class InvestigationPlanner:
    """Build deterministic execution plans from intent + target + registry."""

    def __init__(self, capabilities: CapabilityRegistry | None = None) -> None:
        self.capabilities = capabilities or CapabilityRegistry()
        for cap in BUILTIN_CAPABILITIES:
            if cap.name not in self.capabilities._capabilities:  # noqa: SLF001
                self.capabilities._capabilities[cap.name] = cap  # noqa: SLF001

    def plan(
        self,
        intent: InvestigationIntent,
        *,
        question: str,
        target: dict[str, Any] | None = None,
        deselected_tools: list[str] | None = None,
        available_tools: list[str] | None = None,
    ) -> ExecutionPlan:
        """Produce a structured ExecutionPlan (JSON-serializable)."""
        started = time.perf_counter()
        catalog = {c.name for c in BUILTIN_CAPABILITIES}
        available = set(available_tools) if available_tools is not None else (
            set(self.capabilities._tools) or catalog  # noqa: SLF001
        )
        if not available:
            available = set(tools_for_intent(intent)) | catalog

        discovered = self.capabilities.tools_for_intent(intent.key)
        base_tools = discovered or tools_for_intent(intent)
        ordered: list[str] = []
        for name in tools_for_intent(intent):
            if name in available and name not in ordered:
                ordered.append(name)
        for name in base_tools:
            if name in available and name not in ordered:
                ordered.append(name)

        optional = {t for t in _OPTIONAL_BY_INTENT.get(intent.key, ()) if t in ordered}
        required = [t for t in ordered if t not in optional]
        optional_list = [t for t in ordered if t in optional]

        steps: list[PlanStep] = []
        evidence_needed: list[str] = []
        parallel_tools = [t for t in ordered if t not in {"search", "report", "dashboard"}]
        for idx, tool in enumerate(ordered, start=1):
            needs = list(_EVIDENCE_BY_TOOL.get(tool, [tool]))
            evidence_needed.extend(n for n in needs if n not in evidence_needed)
            in_parallel = tool in parallel_tools and len(parallel_tools) > 1
            steps.append(
                PlanStep(
                    tool=tool,
                    order=idx,
                    priority="optional" if tool in optional else "required",
                    mode="parallel" if in_parallel else "sequential",
                    parallel_group=1 if in_parallel else None,
                    reason=self._reason(tool, intent),
                    estimated_ms=_EST_MS.get(tool, 150),
                    evidence_needed=needs,
                )
            )

        deselected = [t for t in (deselected_tools or []) if t in optional]
        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:12]}",
            intent_key=intent.key,
            intent_label=intent.label,
            target=dict(target or {}),
            question=(question or "").strip(),
            required_tools=required,
            optional_tools=optional_list,
            steps=steps,
            evidence_needed=evidence_needed,
            expected_output=_EXPECTED_OUTPUT.get(
                intent.key, "Evidence-backed investigation response."
            ),
            estimated_ms=sum(s.estimated_ms for s in steps if s.tool not in deselected),
            estimated_evidence_count=max(3, len(evidence_needed) * 2),
            deselected_tools=deselected,
            metadata={
                "planning_ms": round((time.perf_counter() - started) * 1000, 2),
                "planner": "InvestigationPlanner",
                "registry_driven": True,
            },
        )

    def preview(
        self,
        intent: InvestigationIntent,
        *,
        question: str,
        target: dict[str, Any] | None = None,
        available_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Plan preview for analysts before execution."""
        plan = self.plan(
            intent,
            question=question,
            target=target,
            available_tools=available_tools,
        )
        return {
            "intent": plan.intent_key,
            "intent_label": plan.intent_label,
            "required_tools": plan.required_tools,
            "optional_tools": plan.optional_tools,
            "estimated_execution_ms": plan.estimated_ms,
            "estimated_evidence_count": plan.estimated_evidence_count,
            "evidence_needed": plan.evidence_needed,
            "expected_output": plan.expected_output,
            "steps": [s.to_dict() for s in plan.steps],
            "plan": plan.to_dict(),
        }

    @staticmethod
    def _reason(tool: str, intent: InvestigationIntent) -> str:
        cap = next((c for c in BUILTIN_CAPABILITIES if c.name == tool), None)
        if cap:
            return cap.description
        return f"Collect {tool} evidence for {intent.label}."
