"""Investigation plan data models — structured JSON for the planner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


StepMode = Literal["sequential", "parallel"]
StepPriority = Literal["required", "optional"]


@dataclass(slots=True)
class PlanStep:
    """One tool step in an execution plan."""

    tool: str
    order: int
    priority: StepPriority = "required"
    mode: StepMode = "sequential"
    parallel_group: int | None = None
    reason: str = ""
    estimated_ms: int = 200
    evidence_needed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionPlan:
    """Structured investigation plan produced by InvestigationPlanner.

    The LLM never sees how retrieval works — only the eventual evidence package.
    """

    plan_id: str
    intent_key: str
    intent_label: str
    target: dict[str, Any] = field(default_factory=dict)
    question: str = ""
    required_tools: list[str] = field(default_factory=list)
    optional_tools: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)
    evidence_needed: list[str] = field(default_factory=list)
    expected_output: str = ""
    estimated_ms: int = 0
    estimated_evidence_count: int = 0
    deselected_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def active_steps(self) -> list[PlanStep]:
        skip = set(self.deselected_tools)
        return [s for s in self.steps if s.tool not in skip]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "intent_key": self.intent_key,
            "intent_label": self.intent_label,
            "target": dict(self.target),
            "question": self.question,
            "required_tools": list(self.required_tools),
            "optional_tools": list(self.optional_tools),
            "steps": [s.to_dict() for s in self.steps],
            "evidence_needed": list(self.evidence_needed),
            "expected_output": self.expected_output,
            "estimated_ms": self.estimated_ms,
            "estimated_evidence_count": self.estimated_evidence_count,
            "deselected_tools": list(self.deselected_tools),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ToolRunRecord:
    """Observable record of one tool execution."""

    tool: str
    ok: bool
    latency_ms: float = 0.0
    summary: str = ""
    error: str | None = None
    cached: bool = False
    confidence: float | None = None
    freshness: float | None = None
    completeness: float | None = None
    impact: str = ""
    data_preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkflowTrace:
    """End-to-end investigation workflow for analyst transparency."""

    user_query: str = ""
    detected_intent: str = ""
    intent_label: str = ""
    plan: dict[str, Any] = field(default_factory=dict)
    tools_executed: list[dict[str, Any]] = field(default_factory=list)
    evidence_count: int = 0
    context_chars: int = 0
    prompt_chars: int = 0
    model_used: str = ""
    response_generated: bool = False
    planning_ms: float = 0.0
    total_tool_ms: float = 0.0
    explain_ms: float = 0.0
    total_ms: float = 0.0
    validation: dict[str, Any] = field(default_factory=dict)
    stages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
