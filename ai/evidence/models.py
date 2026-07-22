"""Evidence model — every AI answer references Evidence objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Evidence:
    """One evidence unit backing an AI response."""

    id: str
    source: str
    environment: str = "live"
    timestamp: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    keywords: list[str] = field(default_factory=list)
    risk: dict[str, Any] | None = None
    behavior: dict[str, Any] | None = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationship: dict[str, Any] | None = None
    confidence: float = 0.0
    citation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_retrieved(cls, item: dict[str, Any], *, environment: str = "live") -> "Evidence":
        return cls(
            id=str(item.get("id") or item.get("chunk_id") or uuid4()),
            source=str(item.get("source_type") or item.get("source") or "message"),
            environment=environment,
            timestamp=item.get("timestamp"),
            conversation_id=item.get("conversation_id"),
            message_id=str(item.get("source_id") or item.get("message_id") or ""),
            keywords=list(item.get("keywords") or []),
            risk=item.get("risk"),
            behavior=item.get("behavior"),
            entities=list(item.get("entities") or []),
            relationship=item.get("relationship"),
            confidence=float(item.get("score") or item.get("confidence") or 0.0),
            citation=str(item.get("label") or item.get("citation") or ""),
            metadata=dict(item.get("metadata") or {}),
            text=str(item.get("snippet") or item.get("text") or "")[:500],
        )
