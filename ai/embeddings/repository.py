"""MongoDB persistence for AI embeddings (``ai_embeddings`` collection only).

Read/write is isolated from scrape paths. Core collections are never modified.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

from ai.models.schemas import EmbeddingRecord

logger = logging.getLogger("ai.embeddings.repository")

DEFAULT_COLLECTION = "ai_embeddings"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EmbeddingRepository:
    """Store embedding vectors + metadata with content-hash deduplication."""

    def __init__(
        self,
        db: MongoDatabase,
        *,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.db = db
        self.collection_name = collection_name
        self.collection: Collection = db[collection_name]

    def ensure_indexes(self) -> None:
        """Create indexes used for dedup and source lookups."""
        self.collection.create_index(
            [("content_hash", 1), ("embedding_model", 1)],
            unique=True,
            name="uq_ai_embedding_hash_model",
        )
        self.collection.create_index([("chunk_id", 1)], name="ix_ai_embedding_chunk")
        self.collection.create_index(
            [("metadata.source_type", 1), ("metadata.source_id", 1)],
            name="ix_ai_embedding_source",
        )
        self.collection.create_index(
            [("metadata.message_row_id", 1)],
            name="ix_ai_embedding_message_row",
        )

    def existing_hashes(
        self,
        hashes: Sequence[str],
        *,
        embedding_model: str,
    ) -> set[str]:
        """Return content hashes already stored for ``embedding_model``."""
        values = [h for h in hashes if h]
        if not values:
            return set()
        cursor = self.collection.find(
            {
                "content_hash": {"$in": list(values)},
                "embedding_model": embedding_model,
            },
            {"content_hash": 1},
        )
        return {str(doc["content_hash"]) for doc in cursor if doc.get("content_hash")}

    def upsert_records(self, records: Sequence[EmbeddingRecord]) -> int:
        """Upsert embedding records keyed by ``(content_hash, embedding_model)``."""
        written = 0
        now = _utcnow()
        for record in records:
            meta = dict(record.metadata or {})
            digest = str(meta.get("content_hash") or getattr(record, "content_hash", "") or "")
            if not digest:
                logger.warning(
                    "skip_embedding_without_hash",
                    extra={"ai_chunk_id": record.chunk_id},
                )
                continue

            doc = {
                "chunk_id": record.chunk_id,
                "content_hash": digest,
                "embedding_model": record.embedding_model,
                "vector": list(record.vector),
                "text": meta.get("text") or getattr(record, "text", "") or "",
                "source_type": meta.get("source_type"),
                "source_id": meta.get("source_id"),
                "metadata": meta,
                "updated_at": now,
            }
            result = self.collection.update_one(
                {
                    "content_hash": digest,
                    "embedding_model": record.embedding_model,
                },
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            if result.upserted_id is not None or result.modified_count:
                written += 1
        return written

    def count(self, *, embedding_model: str | None = None) -> int:
        query: dict[str, Any] = {}
        if embedding_model:
            query["embedding_model"] = embedding_model
        return int(self.collection.count_documents(query))

    def delete_by_model(self, embedding_model: str) -> int:
        """Delete all embeddings for a model (rebuild helper)."""
        result = self.collection.delete_many({"embedding_model": embedding_model})
        return int(result.deleted_count)
