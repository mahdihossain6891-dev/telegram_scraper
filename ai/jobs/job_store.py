"""Job status persistence for AI background workers (``ai_jobs`` only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database as MongoDatabase

from ai.models.schemas import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStore:
    """Track asynchronous AI jobs without touching core collections."""

    def __init__(self, db: MongoDatabase, *, collection_name: str = "ai_jobs") -> None:
        self.collection = db[collection_name]

    def ensure_indexes(self) -> None:
        self.collection.create_index([("job_type", 1), ("created_at", -1)])
        self.collection.create_index([("state", 1)])

    def create(self, job_type: str, *, detail: str = "") -> JobStatus:
        now = _utcnow()
        status = JobStatus(
            job_id=str(uuid4()),
            job_type=job_type,
            state="queued",
            detail=detail,
            created_at=now,
            updated_at=now,
            stats={},
        )
        self.collection.insert_one(_to_doc(status))
        return status

    def update(
        self,
        job_id: str,
        *,
        state: str | None = None,
        detail: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> JobStatus | None:
        updates: dict[str, Any] = {"updated_at": _utcnow()}
        if state is not None:
            updates["state"] = state
        if detail is not None:
            updates["detail"] = detail
        if stats is not None:
            updates["stats"] = stats
        doc = self.collection.find_one_and_update(
            {"_id": job_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return _from_doc(doc) if doc else None

    def get(self, job_id: str) -> JobStatus | None:
        doc = self.collection.find_one({"_id": job_id})
        return _from_doc(doc) if doc else None


class IndexCursorStore:
    """Persists incremental indexing watermarks (``ai_index_state``)."""

    def __init__(
        self,
        db: MongoDatabase,
        *,
        collection_name: str = "ai_index_state",
    ) -> None:
        self.collection = db[collection_name]

    def get_after_row_id(self, key: str = "message_embeddings") -> int | None:
        doc = self.collection.find_one({"_id": key})
        if not doc:
            return None
        value = doc.get("after_row_id")
        return int(value) if value is not None else None

    def set_after_row_id(self, after_row_id: int, *, key: str = "message_embeddings") -> None:
        self.collection.update_one(
            {"_id": key},
            {
                "$set": {
                    "after_row_id": int(after_row_id),
                    "updated_at": _utcnow(),
                }
            },
            upsert=True,
        )

    def reset(self, *, key: str = "message_embeddings") -> None:
        self.collection.delete_one({"_id": key})


def _to_doc(status: JobStatus) -> dict[str, Any]:
    return {
        "_id": status.job_id,
        "job_type": status.job_type,
        "state": status.state,
        "detail": status.detail,
        "created_at": status.created_at,
        "updated_at": status.updated_at,
        "stats": dict(status.stats or {}),
    }


def _from_doc(doc: dict[str, Any]) -> JobStatus:
    return JobStatus(
        job_id=str(doc.get("_id") or doc.get("job_id")),
        job_type=str(doc.get("job_type") or ""),
        state=str(doc.get("state") or ""),
        detail=str(doc.get("detail") or ""),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        stats=dict(doc.get("stats") or {}),
    )
