"""Evidence DTOs used by the RAG pipeline (never expose DB handles to the LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvidenceItem:
    """One retrieved evidence unit after vector search + optional Mongo hydration."""

    chunk_id: str
    score: float
    text: str
    source_type: str = "message"
    source_id: str = ""
    citation_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    mongo_record: dict[str, Any] | None = None
