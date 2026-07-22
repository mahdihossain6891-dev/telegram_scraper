"""Memory types for Sébastien."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MemoryKind = Literal[
    "session",
    "conversation",
    "investigation",
    "pinned_evidence",
    "bookmark",
    "saved_query",
    "environment",
]


@dataclass(slots=True)
class MemoryEntry:
    kind: MemoryKind
    key: str
    value: Any
    environment: str = "live"
