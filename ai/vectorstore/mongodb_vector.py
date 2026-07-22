"""MongoDB vector backend — searches the ``ai_embeddings`` collection.

Uses brute-force cosine similarity over stored vectors so the indexer job
(``ai_embeddings``) and FastAPI RAG share the same data without Qdrant.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Sequence

from pymongo.database import Database as MongoDatabase

from ai.vectorstore.base import VectorStore
from ai.vectorstore.errors import VectorStoreConfigurationError, VectorStoreError
from ai.vectorstore.filters import normalize_filters, payload_matches
from ai.vectorstore.models import VectorPoint, VectorSearchHit

logger = logging.getLogger("ai.vectorstore.mongodb")


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class MongoDBVectorStore(VectorStore):
    """Search / upsert vectors persisted in Mongo ``ai_embeddings``."""

    name = "mongodb"

    def __init__(
        self,
        db: MongoDatabase | None = None,
        *,
        collection_name: str = "ai_embeddings",
        embedding_model: str = "",
        connection_uri: str = "",
    ) -> None:
        self.db = db
        self.collection_name = collection_name or "ai_embeddings"
        self.embedding_model = (embedding_model or "").strip()
        self.connection_uri = connection_uri
        self._dimension: int | None = None
        if db is not None:
            self.collection = db[self.collection_name]
        else:
            self.collection = None

    def ensure_ready(self, *, dimension: int) -> None:
        if self.collection is None:
            raise VectorStoreConfigurationError(
                "MongoDBVectorStore requires a database handle. "
                "Pass db= into create_vector_store / RAGPipeline.from_settings.",
                backend=self.name,
            )
        if dimension <= 0:
            raise VectorStoreConfigurationError(
                "dimension must be positive",
                backend=self.name,
            )
        self._dimension = int(dimension)
        self.collection.create_index(
            [("embedding_model", 1), ("chunk_id", 1)],
            name="ix_ai_vec_model_chunk",
        )
        logger.info(
            "mongodb_vector_ready",
            extra={
                "ai_collection": self.collection_name,
                "ai_dimension": dimension,
                "ai_embedding_model": self.embedding_model,
            },
        )

    def insert(self, points: Sequence[VectorPoint]) -> int:
        return self.upsert(points)

    def update(self, points: Sequence[VectorPoint]) -> int:
        return self.upsert(points)

    def upsert(self, points: Sequence[VectorPoint]) -> int:
        if self.collection is None:
            raise VectorStoreConfigurationError(
                "MongoDBVectorStore has no database handle.",
                backend=self.name,
            )
        written = 0
        for point in points:
            if not point.id:
                raise VectorStoreError("VectorPoint.id is required", backend=self.name)
            payload = dict(point.payload or {})
            model = str(
                payload.get("embedding_model") or self.embedding_model or ""
            ).strip()
            doc = {
                "chunk_id": point.id,
                "embedding_model": model,
                "vector": [float(x) for x in point.vector],
                "text": str(payload.get("text") or ""),
                "source_type": payload.get("source_type"),
                "source_id": payload.get("source_id"),
                "metadata": payload,
                "content_hash": payload.get("content_hash") or point.id,
            }
            result = self.collection.update_one(
                {"chunk_id": point.id, "embedding_model": model},
                {"$set": doc},
                upsert=True,
            )
            if result.upserted_id is not None or result.modified_count:
                written += 1
        return written

    def delete(self, ids: Sequence[str]) -> int:
        if self.collection is None:
            raise VectorStoreConfigurationError(
                "MongoDBVectorStore has no database handle.",
                backend=self.name,
            )
        id_list = [str(i) for i in ids if i]
        if not id_list:
            return 0
        query: dict[str, Any] = {"chunk_id": {"$in": id_list}}
        if self.embedding_model:
            query["embedding_model"] = self.embedding_model
        result = self.collection.delete_many(query)
        return int(result.deleted_count)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        if self.collection is None:
            raise VectorStoreConfigurationError(
                "MongoDBVectorStore has no database handle.",
                backend=self.name,
            )
        if top_k <= 0:
            return []
        qvec = [float(x) for x in query_vector]
        if not qvec:
            return []

        query: dict[str, Any] = {"vector": {"$exists": True, "$ne": []}}
        if self.embedding_model:
            query["embedding_model"] = self.embedding_model

        filt = normalize_filters(filters)
        scored: list[VectorSearchHit] = []
        cursor = self.collection.find(
            query,
            {
                "chunk_id": 1,
                "vector": 1,
                "text": 1,
                "source_type": 1,
                "source_id": 1,
                "metadata": 1,
                "embedding_model": 1,
            },
        )
        for doc in cursor:
            payload = dict(doc.get("metadata") or {})
            if doc.get("text") and "text" not in payload:
                payload["text"] = doc.get("text")
            if doc.get("source_type") is not None:
                payload.setdefault("source_type", doc.get("source_type"))
            if doc.get("source_id") is not None:
                payload.setdefault("source_id", doc.get("source_id"))
            if doc.get("embedding_model"):
                payload.setdefault("embedding_model", doc.get("embedding_model"))
            if not payload_matches(payload, filt):
                continue
            vector = doc.get("vector") or []
            if len(vector) != len(qvec):
                continue
            score = _cosine(qvec, vector)
            scored.append(
                VectorSearchHit(
                    id=str(doc.get("chunk_id") or doc.get("_id")),
                    score=float(score),
                    payload=payload,
                )
            )

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[: int(top_k)]
