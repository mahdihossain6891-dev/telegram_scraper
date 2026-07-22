"""Optional adapters — convert embedding records without coupling services.

Importing this module does **not** pull in embedding job logic; it only maps
already-produced ``EmbeddingRecord`` objects into ``VectorPoint`` values.
"""

from __future__ import annotations

from typing import Sequence

from ai.models.schemas import EmbeddingRecord, RetrievalHit
from ai.vectorstore.models import VectorPoint, VectorSearchHit


def embedding_records_to_points(
    records: Sequence[EmbeddingRecord],
) -> list[VectorPoint]:
    """Map embedding records to vector points (id = chunk_id)."""
    points: list[VectorPoint] = []
    for record in records:
        payload = dict(record.metadata or {})
        if record.content_hash:
            payload.setdefault("content_hash", record.content_hash)
        if record.text:
            payload.setdefault("text", record.text)
        payload.setdefault("embedding_model", record.embedding_model)
        points.append(
            VectorPoint(
                id=record.chunk_id,
                vector=list(record.vector),
                payload=payload,
            )
        )
    return points


def search_hits_to_retrieval_hits(
    hits: Sequence[VectorSearchHit],
) -> list[RetrievalHit]:
    """Map store hits to the shared ``RetrievalHit`` DTO used by future RAG."""
    out: list[RetrievalHit] = []
    for hit in hits:
        payload = dict(hit.payload or {})
        text = str(payload.get("text") or "")
        out.append(
            RetrievalHit(
                chunk_id=hit.id,
                score=hit.score,
                text=text,
                metadata=payload,
            )
        )
    return out
