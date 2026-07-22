"""Abstract vector store interface.

Backends implement insert / update / delete / similarity search with optional
metadata filtering. This package is intentionally independent of
``ai.embeddings`` — callers pass ``VectorPoint`` values (or convert records
themselves).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from ai.vectorstore.models import VectorPoint, VectorSearchHit


class VectorStore(ABC):
    """Portable vector persistence + similarity search API."""

    name: str = "base"

    @abstractmethod
    def ensure_ready(self, *, dimension: int) -> None:
        """Ensure the backing collection exists for ``dimension``-length vectors."""

    @abstractmethod
    def insert(self, points: Sequence[VectorPoint]) -> int:
        """Insert new points. Raises if an id already exists (when enforceable)."""

    @abstractmethod
    def update(self, points: Sequence[VectorPoint]) -> int:
        """Update existing points. Raises if an id is missing (when enforceable)."""

    @abstractmethod
    def upsert(self, points: Sequence[VectorPoint]) -> int:
        """Insert or update points by id. Returns number of points written."""

    @abstractmethod
    def delete(self, ids: Sequence[str]) -> int:
        """Delete points by application id. Returns number deleted (best-effort)."""

    @abstractmethod
    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        """Return nearest neighbors, optionally filtered by metadata equality."""

    def count(self) -> int:
        """Optional approximate point count (default unsupported)."""
        raise NotImplementedError(f"{type(self).__name__}.count is not implemented")
