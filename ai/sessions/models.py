"""Investigation session models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class InvestigationSession:
    """One analyst investigation session."""

    session_id: str
    target: dict[str, Any] = field(default_factory=dict)
    environment: str = "live"
    history: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    pinned_items: list[dict[str, Any]] = field(default_factory=list)
    conversation: list[dict[str, Any]] = field(default_factory=list)
    generated_reports: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target": dict(self.target),
            "environment": self.environment,
            "history": list(self.history),
            "evidence": list(self.evidence),
            "pinned_items": list(self.pinned_items),
            "conversation": list(self.conversation),
            "generated_reports": list(self.generated_reports),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": dict(self.metadata),
        }
