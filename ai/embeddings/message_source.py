"""Read-only source of flagged Telegram messages for AI indexing.

All messages in the platform MongoDB are keyword-gated (flagged). This module
never writes to ``messages`` or other core collections.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from pymongo.database import Database as MongoDatabase

logger = logging.getLogger("ai.embeddings.message_source")


class FlaggedMessageSource:
    """Iterate flagged messages with text suitable for embedding."""

    def __init__(self, db: MongoDatabase) -> None:
        self.db = db
        self.messages = db["messages"]

    def iter_messages(
        self,
        *,
        after_row_id: int | None = None,
        limit: int | None = None,
        batch_size: int = 100,
    ) -> Iterator[dict[str, Any]]:
        """Yield message documents that have non-empty text.

        Args:
            after_row_id: Exclusive lower bound on ``_id`` for incremental runs.
            limit: Optional max number of messages to yield.
            batch_size: Cursor batch size (does not affect scrape).
        """
        query: dict[str, Any] = {
            "text": {"$exists": True, "$nin": [None, ""]},
        }
        if after_row_id is not None:
            query["_id"] = {"$gt": after_row_id}

        cursor = (
            self.messages.find(query)
            .sort([("_id", 1)])
            .batch_size(max(1, batch_size))
        )
        yielded = 0
        for doc in cursor:
            text = (doc.get("text") or "").strip()
            if not text:
                continue
            yield doc
            yielded += 1
            if limit is not None and yielded >= limit:
                break

        logger.debug(
            "flagged_messages_iterated",
            extra={
                "ai_yielded": yielded,
                "ai_after_row_id": after_row_id,
                "ai_limit": limit,
            },
        )

    def count_with_text(self) -> int:
        return int(
            self.messages.count_documents(
                {"text": {"$exists": True, "$nin": [None, ""]}}
            )
        )
