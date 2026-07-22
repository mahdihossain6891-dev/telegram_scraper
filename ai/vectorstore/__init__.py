"""Vector storage abstraction (Phase 5).

Public API::

    from ai.vectorstore import (
        VectorStore,
        VectorPoint,
        VectorStoreFactory,
        create_vector_store,
    )

    store = create_vector_store()  # from AI_VECTOR_BACKEND
    store.ensure_ready(dimension=384)
    store.upsert([VectorPoint(id="a", vector=[...], payload={"chat_id": 1})])
    hits = store.search(query, top_k=5, filters={"chat_id": 1})
"""

from __future__ import annotations

from .adapters import embedding_records_to_points, search_hits_to_retrieval_hits
from .base import VectorStore
from .errors import (
    VectorStoreConfigurationError,
    VectorStoreError,
    VectorStoreHTTPError,
    VectorStoreNotFoundError,
)
from .factory import VectorStoreFactory, create_vector_store
from .filters import normalize_filters, payload_matches
from .memory import InMemoryVectorStore
from .models import VectorPoint, VectorSearchHit
from .qdrant import QdrantVectorStore, build_qdrant_filter

__all__ = [
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "VectorPoint",
    "VectorSearchHit",
    "VectorStore",
    "VectorStoreConfigurationError",
    "VectorStoreError",
    "VectorStoreFactory",
    "VectorStoreHTTPError",
    "VectorStoreNotFoundError",
    "build_qdrant_filter",
    "create_vector_store",
    "embedding_records_to_points",
    "normalize_filters",
    "payload_matches",
    "search_hits_to_retrieval_hits",
]
