"""ProcessingContext — single intelligence object flowing through stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.models import MessageEvent


@dataclass(slots=True)
class ProcessingContext:
    """Mutable context enriched by each pipeline stage."""

    event: MessageEvent
    session_id: str
    tick: int
    normalized_text: str = ""
    keywords: list[str] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "normal"
    behavior: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    alert: dict[str, Any] | None = None
    persisted: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    stage_durations_ms: dict[str, float] = field(default_factory=dict)
    stage_errors: dict[str, str] = field(default_factory=dict)
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tick": self.tick,
            "message_id": self.event.message_id,
            "normalized_text": self.normalized_text,
            "keywords": list(self.keywords),
            "entities": list(self.entities),
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "behavior": dict(self.behavior),
            "relationships": list(self.relationships),
            "alert": dict(self.alert) if self.alert else None,
            "persisted": self.persisted,
            "metrics": dict(self.metrics),
            "stage_durations_ms": dict(self.stage_durations_ms),
            "stage_errors": dict(self.stage_errors),
        }
