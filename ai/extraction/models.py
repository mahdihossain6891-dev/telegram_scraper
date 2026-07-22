"""AI entity extraction models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


AI_ENTITY_TYPES: tuple[str, ...] = (
    "phone",
    "wallet",
    "username",
    "organization",
    "location",
    "person",
    "url",
    "email",
)


@dataclass(slots=True)
class AIEntityCandidate:
    """One AI-extracted entity before / after merge."""

    entity_type: str
    entity_value: str
    confidence: float
    start_offset: int | None = None
    end_offset: int | None = None
    matched_regex: bool = False
    source: str = "ai"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_value": self.entity_value,
            "confidence": self.confidence,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "matched_regex": self.matched_regex,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AIEntityRecord:
    """Persisted AI entity document (``ai_entities`` only)."""

    message_row_id: int
    entity_type: str
    entity_value: str
    normalized_value: str
    confidence: float
    matched_regex: bool = False
    start_offset: int | None = None
    end_offset: int | None = None
    chat_id: int | None = None
    message_id: int | None = None
    source: str = "ai"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
