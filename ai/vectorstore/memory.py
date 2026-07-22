"""In-memory VectorStore for tests and local dry-runs (no external deps)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from ai.vectorstore.base import VectorStore
from ai.vectorstore.errors import (
    VectorStoreConfigurationError,
    VectorStoreNotFoundError,
)
from ai.vectorstore.filters import normalize_filters, payload_matches
from ai.vectorstore.models import VectorPoint, VectorSearchHit


class InMemoryVectorStore(VectorStore):
    """Cosine-similarity store kept entirely in process memory."""

    name = "memory"

    def __init__(self) -> None:
        self._points: dict[str, VectorPoint] = {}
        self._dimension: int | None = None

    def ensure_ready(self, *, dimension: int) -> None:
        if dimension <= 0:
            raise VectorStoreConfigurationError(
                "dimension must be > 0", backend=self.name
            )
        if self._dimension is None:
            self._dimension = dimension
        elif self._dimension != dimension:
            raise VectorStoreConfigurationError(
                f"dimension mismatch: store={self._dimension}, requested={dimension}",
                backend=self.name,
            )

    def insert(self, points: Sequence[VectorPoint]) -> int:
        self._validate(points)
        for point in points:
            if point.id in self._points:
                raise VectorStoreNotFoundError(
                    f"Point already exists: {point.id}",
                    backend=self.name,
                )
        return self._write(points)

    def update(self, points: Sequence[VectorPoint]) -> int:
        self._validate(points)
        for point in points:
            if point.id not in self._points:
                raise VectorStoreNotFoundError(
                    f"Point not found for update: {point.id}",
                    backend=self.name,
                )
        return self._write(points)

    def upsert(self, points: Sequence[VectorPoint]) -> int:
        self._validate(points)
        return self._write(points)

    def delete(self, ids: Sequence[str]) -> int:
        deleted = 0
        for point_id in ids:
            if point_id in self._points:
                del self._points[point_id]
                deleted += 1
        return deleted

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        if top_k <= 0:
            return []
        query = [float(x) for x in query_vector]
        if self._dimension is not None and len(query) != self._dimension:
            raise VectorStoreConfigurationError(
                f"query dimension {len(query)} != store dimension {self._dimension}",
                backend=self.name,
            )
        filt = normalize_filters(filters)
        scored: list[VectorSearchHit] = []
        for point in self._points.values():
            if not payload_matches(point.payload, filt):
                continue
            score = _cosine(query, point.vector)
            scored.append(
                VectorSearchHit(
                    id=point.id,
                    score=score,
                    payload=dict(point.payload),
                    vector=list(point.vector),
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._points)

    def _validate(self, points: Sequence[VectorPoint]) -> None:
        if not points:
            return
        dim = len(points[0].vector)
        if self._dimension is None:
            self._dimension = dim
        for point in points:
            if not point.id:
                raise VectorStoreConfigurationError(
                    "VectorPoint.id is required", backend=self.name
                )
            if len(point.vector) != self._dimension:
                raise VectorStoreConfigurationError(
                    f"vector dimension mismatch for id={point.id}",
                    backend=self.name,
                )

    def _write(self, points: Sequence[VectorPoint]) -> int:
        for point in points:
            self._points[point.id] = VectorPoint(
                id=point.id,
                vector=[float(x) for x in point.vector],
                payload=dict(point.payload or {}),
            )
        return len(points)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
