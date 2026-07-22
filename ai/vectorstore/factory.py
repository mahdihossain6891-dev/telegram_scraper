"""Vector store factory — selects backends from ``AI_*`` settings."""

from __future__ import annotations

import logging

from ai.config import AISettings, get_ai_settings
from ai.vectorstore.base import VectorStore
from ai.vectorstore.errors import VectorStoreConfigurationError
from ai.vectorstore.memory import InMemoryVectorStore
from ai.vectorstore.models import VectorPoint, VectorSearchHit
from ai.vectorstore.mongodb_vector import MongoDBVectorStore
from ai.vectorstore.qdrant import QdrantVectorStore

logger = logging.getLogger("ai.vectorstore.factory")


class DisabledVectorStore(VectorStore):
    """No-op store when ``AI_VECTOR_BACKEND=none``."""

    name = "none"

    def ensure_ready(self, *, dimension: int) -> None:
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )

    def insert(self, points):
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )

    def update(self, points):
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )

    def upsert(self, points):
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )

    def delete(self, ids):
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )

    def search(self, query_vector, *, top_k=8, filters=None):
        raise VectorStoreConfigurationError(
            "Vector store is disabled (AI_VECTOR_BACKEND=none).",
            backend=self.name,
        )


class VectorStoreFactory:
    """Build a ``VectorStore`` from ``AISettings``."""

    def __init__(self, settings: AISettings | None = None) -> None:
        self.settings = settings or get_ai_settings()

    def create(self, db=None) -> VectorStore:
        cfg = self.settings
        backend = cfg.vector_backend
        if backend == "none":
            logger.info("vector_store_disabled")
            return DisabledVectorStore()
        if backend == "memory":
            logger.info("vector_store_selected", extra={"ai_backend": "memory"})
            return InMemoryVectorStore()
        if backend == "mongodb":
            logger.info("vector_store_selected", extra={"ai_backend": "mongodb"})
            return MongoDBVectorStore(
                db,
                collection_name=cfg.vector_collection or "ai_embeddings",
                embedding_model=cfg.embedding_model,
            )
        if backend == "qdrant":
            logger.info(
                "vector_store_selected",
                extra={
                    "ai_backend": "qdrant",
                    "ai_vector_url": cfg.vector_url or "http://127.0.0.1:6333",
                    "ai_collection": cfg.vector_collection,
                },
            )
            return QdrantVectorStore(
                url=cfg.vector_url,
                collection_name=cfg.vector_collection,
                api_key=cfg.api_key,
                timeout_seconds=cfg.request_timeout_seconds,
            )
        raise VectorStoreConfigurationError(
            f"Unsupported AI_VECTOR_BACKEND: {backend!r}",
            backend=str(backend),
        )


def create_vector_store(settings: AISettings | None = None, db=None) -> VectorStore:
    """Convenience wrapper around ``VectorStoreFactory.create``."""
    return VectorStoreFactory(settings).create(db=db)

# Re-export hit/point names for type checkers using the factory module.
__all__ = [
    "DisabledVectorStore",
    "VectorPoint",
    "VectorSearchHit",
    "VectorStoreFactory",
    "create_vector_store",
]
