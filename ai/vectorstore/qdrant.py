"""Qdrant VectorStore via the HTTP API (stdlib only — no embedding coupling)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from ai.vectorstore.base import VectorStore
from ai.vectorstore.errors import (
    VectorStoreConfigurationError,
    VectorStoreHTTPError,
    VectorStoreNotFoundError,
)
from ai.vectorstore.filters import normalize_filters
from ai.vectorstore.models import VectorPoint, VectorSearchHit

logger = logging.getLogger("ai.vectorstore.qdrant")

_DEFAULT_URL = "http://127.0.0.1:6333"
_APP_ID_KEY = "app_id"


def normalize_qdrant_url(url: str | None) -> str:
    raw = (url or "").strip() or _DEFAULT_URL
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise VectorStoreConfigurationError(
            f"Invalid AI_VECTOR_URL for Qdrant: {url!r}",
            backend="qdrant",
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def qdrant_point_uuid(app_id: str) -> str:
    """Map an application string id to a stable Qdrant UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-vector:{app_id}"))


def build_qdrant_filter(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate equality metadata filters to a Qdrant Filter body."""
    normalized = normalize_filters(filters)
    if not normalized:
        return None
    must: list[dict[str, Any]] = []
    for key, value in normalized.items():
        must.append({"key": key, "match": {"value": value}})
    return {"must": must}


class QdrantVectorStore(VectorStore):
    """Qdrant-backed vector store using REST endpoints.

    Independence notes:
    - Does not import ``ai.embeddings``
    - Accepts only ``VectorPoint`` / raw vectors
    - Application ids are stored in payload[``app_id``]; Qdrant point ids are UUIDs
    """

    name = "qdrant"

    def __init__(
        self,
        *,
        url: str = "",
        collection_name: str = "ai_embeddings",
        api_key: str = "",
        timeout_seconds: float = 30.0,
        distance: str = "Cosine",
    ) -> None:
        self.base_url = normalize_qdrant_url(url)
        self.collection_name = collection_name or "ai_embeddings"
        self.api_key = api_key or ""
        self.timeout_seconds = float(timeout_seconds)
        self.distance = distance
        self._dimension: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_ready(self, *, dimension: int) -> None:
        if dimension <= 0:
            raise VectorStoreConfigurationError(
                "dimension must be > 0", backend=self.name
            )
        self._dimension = dimension
        if self._collection_exists():
            return
        self._request(
            "PUT",
            f"/collections/{self.collection_name}",
            {
                "vectors": {
                    "size": dimension,
                    "distance": self.distance,
                }
            },
        )
        logger.info(
            "qdrant_collection_created",
            extra={
                "ai_collection": self.collection_name,
                "ai_dimension": dimension,
            },
        )

    def insert(self, points: Sequence[VectorPoint]) -> int:
        if not points:
            return 0
        existing = self._existing_app_ids([p.id for p in points])
        conflicts = [pid for pid in (p.id for p in points) if pid in existing]
        if conflicts:
            raise VectorStoreNotFoundError(
                f"Points already exist: {conflicts[:5]}",
                backend=self.name,
                details={"ids": conflicts},
            )
        return self._upsert_points(points)

    def update(self, points: Sequence[VectorPoint]) -> int:
        if not points:
            return 0
        existing = self._existing_app_ids([p.id for p in points])
        missing = [p.id for p in points if p.id not in existing]
        if missing:
            raise VectorStoreNotFoundError(
                f"Points not found for update: {missing[:5]}",
                backend=self.name,
                details={"ids": missing},
            )
        return self._upsert_points(points)

    def upsert(self, points: Sequence[VectorPoint]) -> int:
        if not points:
            return 0
        return self._upsert_points(points)

    def delete(self, ids: Sequence[str]) -> int:
        values = [i for i in ids if i]
        if not values:
            return 0
        point_ids = [qdrant_point_uuid(app_id) for app_id in values]
        self._request(
            "POST",
            f"/collections/{self.collection_name}/points/delete?wait=true",
            {"points": point_ids},
        )
        return len(values)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        if top_k <= 0:
            return []
        body: dict[str, Any] = {
            "vector": [float(x) for x in query_vector],
            "limit": int(top_k),
            "with_payload": True,
            "with_vector": False,
        }
        qfilter = build_qdrant_filter(filters)
        if qfilter:
            body["filter"] = qfilter

        data = self._request(
            "POST",
            f"/collections/{self.collection_name}/points/search",
            body,
        )
        results = data.get("result") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []

        hits: list[VectorSearchHit] = []
        for row in results:
            if not isinstance(row, dict):
                continue
            payload = dict(row.get("payload") or {})
            app_id = str(payload.get(_APP_ID_KEY) or row.get("id") or "")
            hits.append(
                VectorSearchHit(
                    id=app_id,
                    score=float(row.get("score") or 0.0),
                    payload=payload,
                )
            )
        return hits

    def count(self) -> int:
        data = self._request(
            "POST",
            f"/collections/{self.collection_name}/points/count",
            {"exact": True},
        )
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict) and "count" in result:
            return int(result["count"])
        return 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _upsert_points(self, points: Sequence[VectorPoint]) -> int:
        dim = len(points[0].vector)
        if self._dimension is None:
            self.ensure_ready(dimension=dim)
        elif dim != self._dimension:
            raise VectorStoreConfigurationError(
                f"vector dimension {dim} != collection dimension {self._dimension}",
                backend=self.name,
            )

        qpoints = []
        for point in points:
            if not point.id:
                raise VectorStoreConfigurationError(
                    "VectorPoint.id is required", backend=self.name
                )
            if len(point.vector) != dim:
                raise VectorStoreConfigurationError(
                    f"inconsistent vector sizes in batch (id={point.id})",
                    backend=self.name,
                )
            payload = dict(point.payload or {})
            payload[_APP_ID_KEY] = point.id
            qpoints.append(
                {
                    "id": qdrant_point_uuid(point.id),
                    "vector": [float(x) for x in point.vector],
                    "payload": payload,
                }
            )

        self._request(
            "PUT",
            f"/collections/{self.collection_name}/points?wait=true",
            {"points": qpoints},
        )
        logger.info(
            "qdrant_upsert",
            extra={
                "ai_collection": self.collection_name,
                "ai_count": len(qpoints),
            },
        )
        return len(qpoints)

    def _existing_app_ids(self, app_ids: Sequence[str]) -> set[str]:
        values = [i for i in app_ids if i]
        if not values:
            return set()
        data = self._request(
            "POST",
            f"/collections/{self.collection_name}/points/scroll",
            {
                "filter": {
                    "must": [
                        {
                            "key": _APP_ID_KEY,
                            "match": {"any": values},
                        }
                    ]
                },
                "limit": max(len(values), 1),
                "with_payload": [_APP_ID_KEY],
                "with_vector": False,
            },
        )
        result = data.get("result") if isinstance(data, dict) else None
        points = result.get("points") if isinstance(result, dict) else None
        found: set[str] = set()
        if isinstance(points, list):
            for point in points:
                if not isinstance(point, dict):
                    continue
                payload = point.get("payload") or {}
                if isinstance(payload, dict) and payload.get(_APP_ID_KEY):
                    found.add(str(payload[_APP_ID_KEY]))
        return found

    def _collection_exists(self) -> bool:
        try:
            self._request("GET", f"/collections/{self.collection_name}")
            return True
        except VectorStoreHTTPError as exc:
            if exc.details.get("status_code") == 404:
                return False
            raise

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key

        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
            raise VectorStoreHTTPError(
                f"Qdrant HTTP {exc.code} for {method} {path}",
                backend=self.name,
                details={"status_code": exc.code, "body": body[:2000], "url": url},
            ) from exc
        except URLError as exc:
            raise VectorStoreHTTPError(
                f"Could not reach Qdrant at {self.base_url}: {exc.reason!r}",
                backend=self.name,
                details={"url": url},
            ) from exc

        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VectorStoreHTTPError(
                "Qdrant returned invalid JSON",
                backend=self.name,
                details={"status_code": status, "body": raw[:500]},
            ) from exc
        if not isinstance(parsed, dict):
            raise VectorStoreHTTPError(
                "Qdrant JSON was not an object",
                backend=self.name,
                details={"status_code": status},
            )
        return parsed
