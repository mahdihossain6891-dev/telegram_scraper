"""Structured AI response — internal JSON, UI renders markdown."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class StructuredCitation:
    label: str
    source_type: str
    source_id: str
    snippet: str = ""


@dataclass(slots=True)
class RecommendedAction:
    id: str
    label: str
    reason: str
    prompt: str = ""


@dataclass(slots=True)
class StructuredResponse:
    """Canonical Sébastien response shape — never free-form markdown from LLM."""

    executive_summary: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: dict[str, Any] = field(default_factory=dict)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[RecommendedAction] = field(default_factory=list)
    citations: list[StructuredCitation] = field(default_factory=list)
    intent: str = ""
    intent_label: str = ""
    refused: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executive_summary": self.executive_summary,
            "evidence": list(self.evidence),
            "confidence": dict(self.confidence),
            "timeline": list(self.timeline),
            "relationships": list(self.relationships),
            "recommended_actions": [asdict(a) for a in self.recommended_actions],
            "citations": [asdict(c) for c in self.citations],
            "intent": self.intent,
            "intent_label": self.intent_label,
            "refused": self.refused,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_investigation_context(cls, ctx: Any) -> "StructuredResponse":
        """Build structured response from InvestigationContext."""
        actions = [
            RecommendedAction(
                id=a.id,
                label=a.label,
                reason=a.reason,
                prompt=a.prompt,
            )
            for a in (ctx.next_actions or [])
        ]
        citations = [
            StructuredCitation(
                label=str(c.get("label") or ""),
                source_type=str(c.get("source_type") or "message"),
                source_id=str(c.get("source_id") or ""),
                snippet=str(c.get("snippet") or "")[:240],
            )
            for c in (ctx.citations or [])
        ]
        conf: dict[str, Any] = {}
        if ctx.confidence:
            conf = {
                "score": ctx.confidence.score,
                "label": ctx.confidence.label,
                "reason": ctx.confidence.reason,
                "factors": dict(ctx.confidence.factors or {}),
            }
        return cls(
            executive_summary=ctx.answer or "",
            evidence=list(ctx.evidence or []),
            confidence=conf,
            timeline=list(ctx.timeline or []),
            relationships=list(ctx.relationships or []),
            recommended_actions=actions,
            citations=citations,
            intent=ctx.intent_key,
            intent_label=ctx.intent_label,
            refused=bool(ctx.refused),
            metadata=ctx.to_metadata() if hasattr(ctx, "to_metadata") else {},
        )
