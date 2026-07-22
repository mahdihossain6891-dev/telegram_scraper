"""Shared schemas for AI artifacts.

These dataclasses describe future wire/storage shapes. Phase 1 defines
structure only — no persistence or validation against MongoDB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AIDocumentChunk:
    """Normalized text chunk prepared for embedding / retrieval."""

    chunk_id: str
    source_type: str
    source_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingRecord:
    """Vector row associated with a document chunk."""

    chunk_id: str
    embedding_model: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    text: str = ""


@dataclass(slots=True)
class RetrievalHit:
    """Single retrieval result from the vector store."""

    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Citation:
    """Evidence pointer returned with generated answers."""

    source_type: str
    source_id: str
    label: str = ""
    snippet: str = ""


@dataclass(slots=True)
class QueryRequest:
    """Analyst question for the RAG engine."""

    question: str
    top_k: int = 8
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QueryResponse:
    """Grounded answer payload returned by ``RAGPipeline``."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: str = "low"
    model: str = ""
    retrieved: list[RetrievalHit] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    raw_completion: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class InsightRecord:
    """Stored AI-generated brief / narrative (future ``ai_insights``)."""

    insight_id: str
    subject_type: str
    subject_id: str
    title: str
    body: str
    citations: list[Citation] = field(default_factory=list)
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JobStatus:
    """Async job bookkeeping (``ai_jobs``)."""

    job_id: str
    job_type: str
    state: str
    detail: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    stats: dict[str, Any] = field(default_factory=dict)