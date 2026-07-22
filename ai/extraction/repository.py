"""Persistence for AI entities (``ai_entities`` collection only).

Never writes to ``extracted_entities``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Sequence

from pymongo.database import Database as MongoDatabase

from ai.extraction.models import AIEntityCandidate, AIEntityRecord
from ai.extraction.normalize import normalize_entity_value

logger = logging.getLogger("ai.extraction.repository")

COLLECTION = "ai_entities"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AIEntityRepository:
    """Store AI-extracted entities with confidence scores."""

    def __init__(
        self,
        db: MongoDatabase,
        *,
        collection_name: str = COLLECTION,
    ) -> None:
        self.db = db
        self.collection = db[collection_name]

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [("message_row_id", 1), ("entity_type", 1), ("normalized_value", 1)],
            unique=True,
            name="uq_ai_entity_msg_type_value",
        )
        self.collection.create_index([("entity_type", 1)], name="ix_ai_entity_type")
        self.collection.create_index([("confidence", -1)], name="ix_ai_entity_confidence")
        self.collection.create_index([("chat_id", 1)], name="ix_ai_entity_chat")

    def upsert_candidates(
        self,
        message_row_id: int,
        candidates: Sequence[AIEntityCandidate],
        *,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> int:
        """Upsert AI entities for one message. Returns number of writes."""
        written = 0
        now = _utcnow()
        for candidate in candidates:
            norm = normalize_entity_value(
                candidate.entity_type, candidate.entity_value
            )
            if not norm:
                continue
            doc = {
                "message_row_id": int(message_row_id),
                "entity_type": candidate.entity_type,
                "entity_value": candidate.entity_value,
                "normalized_value": norm,
                "confidence": float(candidate.confidence),
                "matched_regex": bool(candidate.matched_regex),
                "start_offset": candidate.start_offset,
                "end_offset": candidate.end_offset,
                "chat_id": chat_id,
                "message_id": message_id,
                "source": candidate.source,
                "metadata": dict(candidate.metadata or {}),
                "updated_at": now,
            }
            result = self.collection.update_one(
                {
                    "message_row_id": int(message_row_id),
                    "entity_type": candidate.entity_type,
                    "normalized_value": norm,
                },
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            if result.upserted_id is not None or result.modified_count:
                written += 1
        return written

    def list_for_message(self, message_row_id: int) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"message_row_id": int(message_row_id)}).sort(
                [("confidence", -1)]
            )
        )

    def count(self) -> int:
        return int(self.collection.count_documents({}))
