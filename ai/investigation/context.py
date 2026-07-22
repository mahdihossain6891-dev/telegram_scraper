"""InvestigationContext — structured state for a single investigation turn.

The LLM receives a serialized subset of this object only. It never decides
what evidence exists; tools + the investigation engine populate it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PipelineStatus = Literal[
    "pending",
    "intent_detected",
    "validation_failed",
    "entity_ambiguous",
    "entity_missing",
    "target_required",
    "unknown_intent",
    "no_evidence",
    "ready_for_explain",
    "explained",
    "refused",
]


@dataclass(slots=True)
class NextAction:
    """Recommended follow-up for the analyst."""

    id: str
    label: str
    reason: str
    prompt: str = ""


@dataclass(slots=True)
class ConfidenceAssessment:
    """Evidence-derived confidence — never guessed by the LLM."""

    score: int  # 0–100
    label: Literal["low", "medium", "high"]
    reason: str
    factors: dict[str, Any] = field(default_factory=dict)

    def band(self) -> str:
        return self.label


@dataclass(slots=True)
class InvestigationFinding:
    """Deterministic finding produced by the investigation engine."""

    key: str
    title: str
    summary: str
    value: Any = None
    citation_labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolExecution:
    """Record of one tool run."""

    name: str
    ok: bool
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float | None = None
    cached: bool = False
    confidence: float | None = None
    freshness: float | None = None
    completeness: float | None = None
    impact: str = ""


@dataclass(slots=True)
class InvestigationContext:
    """Full structured investigation state for one analyst turn."""

    question: str
    session_id: str
    intent_key: str = "unknown"
    intent_label: str = "Unknown"
    status: PipelineStatus = "pending"
    subject: dict[str, Any] = field(default_factory=dict)
    entity_resolution: dict[str, Any] = field(default_factory=dict)
    tools_requested: list[str] = field(default_factory=list)
    tool_results: list[ToolExecution] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    findings: list[InvestigationFinding] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    behavior: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    threat_report: dict[str, Any] = field(default_factory=dict)
    confidence: ConfidenceAssessment | None = None
    next_actions: list[NextAction] = field(default_factory=list)
    validation_message: str = ""
    validation_suggestions: list[str] = field(default_factory=list)
    answer: str = ""
    model: str = ""
    refused: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    # Runtime handles for tools (never serialized to the LLM / API clients).
    db: Any = field(default=None, repr=False)
    retriever: Any = field(default=None, repr=False)
    filters: dict[str, Any] = field(default_factory=dict, repr=False)
    top_k: int = field(default=8, repr=False)

    def has_target(self) -> bool:
        return (
            self.subject.get("user_id") is not None
            or self.subject.get("chat_id") is not None
            or self.subject.get("alert_id") is not None
            or self.subject.get("case_id") is not None
        )

    def to_grounding_dict(self) -> dict[str, Any]:
        """Compact payload the LLM may see — never raw DB rows."""
        return {
            "intent": {"key": self.intent_key, "label": self.intent_label},
            "target": {
                k: self.subject.get(k)
                for k in (
                    "subject_type",
                    "subject_id",
                    "user_id",
                    "chat_id",
                    "display_name",
                    "username",
                    "risk_score",
                    "behavior_score",
                )
                if self.subject.get(k) is not None
            },
            "findings": [
                {
                    "key": f.key,
                    "title": f.title,
                    "summary": f.summary,
                    "value": f.value,
                    "citations": list(f.citation_labels),
                }
                for f in self.findings
            ],
            "risk": dict(self.risk) if self.risk else {},
            "behavior": _truncate_dict(self.behavior, depth=2),
            "alerts": self.alerts[:12],
            "timeline": self.timeline[:20],
            "relationships": self.relationships[:20],
            "evidence": self.evidence[:12],
            "confidence": asdict(self.confidence) if self.confidence else None,
            "next_actions": [asdict(a) for a in self.next_actions],
            "tool_summaries": [
                {"name": t.name, "ok": t.ok, "summary": t.summary}
                for t in self.tool_results
            ],
        }

    def to_metadata(self) -> dict[str, Any]:
        conf = asdict(self.confidence) if self.confidence else None
        return {
            "pipeline_status": self.status,
            "intent": self.intent_key,
            "intent_label": self.intent_label,
            "subject": dict(self.subject),
            "entity_resolution": dict(self.entity_resolution),
            "tools_requested": list(self.tools_requested),
            "tool_results": [
                {
                    "name": t.name,
                    "ok": t.ok,
                    "summary": t.summary,
                    "error": t.error,
                    "latency_ms": t.latency_ms,
                    "cached": t.cached,
                    "confidence": t.confidence,
                    "freshness": t.freshness,
                    "completeness": t.completeness,
                    "impact": t.impact,
                }
                for t in self.tool_results
            ],
            "findings": [
                {
                    "key": f.key,
                    "title": f.title,
                    "summary": f.summary,
                    "value": f.value,
                    "citations": list(f.citation_labels),
                }
                for f in self.findings
            ],
            "confidence_detail": conf,
            "next_actions": [asdict(a) for a in self.next_actions],
            "threat_report": dict(self.threat_report) if self.threat_report else {},
            "validation_message": self.validation_message,
            "validation_suggestions": list(self.validation_suggestions),
            **dict(self.metadata),
        }


def _truncate_dict(value: Any, *, depth: int) -> Any:
    if depth <= 0:
        return "…"
    if isinstance(value, dict):
        out = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= 24:
                out["…"] = f"{len(value) - 24} more keys"
                break
            out[str(k)] = _truncate_dict(v, depth=depth - 1)
        return out
    if isinstance(value, list):
        return [_truncate_dict(v, depth=depth - 1) for v in value[:12]]
    if isinstance(value, str) and len(value) > 400:
        return value[:400] + "…"
    return value
