"""Orchestrate AI entity extraction for flagged messages."""

from __future__ import annotations

import logging
from typing import Any

from pymongo.database import Database as MongoDatabase

from ai.extraction.merge import EntityMergeService
from ai.extraction.ner_service import NERService
from ai.extraction.repository import AIEntityRepository

logger = logging.getLogger("ai.extraction.service")


class EntityExtractionService:
    """Read regex entities → AI extract → merge → write ``ai_entities`` only."""

    def __init__(
        self,
        db: MongoDatabase,
        ner: NERService,
        *,
        merger: EntityMergeService | None = None,
        repository: AIEntityRepository | None = None,
    ) -> None:
        self.db = db
        self.ner = ner
        self.merger = merger or EntityMergeService()
        self.repository = repository or AIEntityRepository(db)
        self.messages = db["messages"]
        self.regex_entities = db["extracted_entities"]

    def process_message(self, message: dict[str, Any]) -> dict[str, int]:
        """Extract/merge/store AI entities for one message document."""
        row_id = message.get("_id")
        if row_id is None:
            return {"ai_candidates": 0, "stored": 0, "matched_regex": 0}
        text = (message.get("text") or "").strip()
        if not text:
            return {"ai_candidates": 0, "stored": 0, "matched_regex": 0}

        regex_rows = list(
            self.regex_entities.find({"message_row_id": int(row_id)})
        )
        # Snapshot count to prove we never delete/overwrite regex rows.
        regex_before = len(regex_rows)

        candidates = self.ner.extract(
            text,
            metadata={
                "message_row_id": int(row_id),
                "chat_id": message.get("chat_id"),
                "message_id": message.get("message_id"),
            },
        )
        merged = self.merger.merge(regex_rows, candidates)
        stored = self.repository.upsert_candidates(
            int(row_id),
            merged,
            chat_id=message.get("chat_id"),
            message_id=message.get("message_id"),
        )

        regex_after = self.regex_entities.count_documents(
            {"message_row_id": int(row_id)}
        )
        if regex_after != regex_before:
            logger.error(
                "regex_entities_mutated_unexpectedly",
                extra={
                    "ai_message_row_id": row_id,
                    "ai_before": regex_before,
                    "ai_after": regex_after,
                },
            )

        return {
            "ai_candidates": len(candidates),
            "stored": stored,
            "matched_regex": sum(1 for m in merged if m.matched_regex),
            "regex_unchanged": int(regex_after == regex_before),
        }

    def process_messages(
        self,
        *,
        after_row_id: int | None = None,
        limit: int | None = None,
        batch_size: int = 50,
    ) -> dict[str, int]:
        """Batch-process flagged messages with text."""
        self.repository.ensure_indexes()
        query: dict[str, Any] = {"text": {"$exists": True, "$nin": [None, ""]}}
        if after_row_id is not None:
            query["_id"] = {"$gt": after_row_id}

        stats = {
            "messages_seen": 0,
            "ai_candidates": 0,
            "stored": 0,
            "matched_regex": 0,
        }
        cursor = (
            self.messages.find(query)
            .sort([("_id", 1)])
            .batch_size(max(1, batch_size))
        )
        for doc in cursor:
            stats["messages_seen"] += 1
            result = self.process_message(doc)
            stats["ai_candidates"] += result.get("ai_candidates", 0)
            stats["stored"] += result.get("stored", 0)
            stats["matched_regex"] += result.get("matched_regex", 0)
            if limit is not None and stats["messages_seen"] >= limit:
                break
        return stats
