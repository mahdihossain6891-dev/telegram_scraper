"""Load supporting MongoDB records for RAG (LLM never accesses Mongo)."""

from __future__ import annotations

import logging
from typing import Any

from pymongo.database import Database as MongoDatabase

from ai.rag.evidence import EvidenceItem
from ai.rag.user_enrichment import UserIdentityEnricher
from ai.vectorstore.models import VectorSearchHit

logger = logging.getLogger("ai.rag.mongo_loader")


class MongoEvidenceLoader:
    """Hydrate vector hits with message (and related) documents from MongoDB.

    This is the **only** RAG component that talks to Mongo. The chat model
    receives plain text context assembled later — never a database session.

    Every sender is enriched via ``UserIdentityEnricher`` so all AI features
    (query, investigate, chat, summary, reports) receive human-readable users.
    """

    def __init__(self, db: MongoDatabase | None = None) -> None:
        self.db = db
        self.identity = UserIdentityEnricher(db)

    def hydrate(self, hits: list[VectorSearchHit]) -> list[EvidenceItem]:
        """Turn vector hits into evidence items, enriching from Mongo when possible."""
        items: list[EvidenceItem] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            text = str(payload.get("text") or "").strip()
            source_type = str(payload.get("source_type") or "message")
            source_id = str(payload.get("source_id") or hit.id)
            mongo_doc = self._load_mongo_doc(payload)
            if mongo_doc:
                if not text:
                    text = str(mongo_doc.get("text") or "").strip()
                payload = {
                    **payload,
                    "message_row_id": mongo_doc.get("_id", payload.get("message_row_id")),
                    "chat_id": mongo_doc.get("chat_id", payload.get("chat_id")),
                    "message_id": mongo_doc.get("message_id", payload.get("message_id")),
                    "sender_id": mongo_doc.get("sender_id", payload.get("sender_id")),
                    "risk_score": mongo_doc.get("risk_score", payload.get("risk_score")),
                    "risk_level": mongo_doc.get("risk_level", payload.get("risk_level")),
                    "timestamp": _iso(mongo_doc.get("timestamp"))
                    or payload.get("timestamp"),
                }
                source_id = str(mongo_doc.get("_id") or source_id)

            label = _citation_label(payload, source_type=source_type, source_id=source_id)
            items.append(
                EvidenceItem(
                    chunk_id=hit.id,
                    score=float(hit.score),
                    text=text,
                    source_type=source_type,
                    source_id=source_id,
                    citation_label=label,
                    metadata=payload,
                    mongo_record=mongo_doc,
                )
            )

        self.identity.enrich_evidence_items(items)

        logger.debug(
            "evidence_hydrated",
            extra={
                "ai_hits": len(hits),
                "ai_with_text": sum(1 for i in items if i.text),
                "ai_with_sender": sum(
                    1 for i in items if (i.metadata or {}).get("sender_user")
                ),
            },
        )
        return items

    def _load_mongo_doc(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.db is None:
            return None
        messages = self.db["messages"]
        row_id = payload.get("message_row_id")
        if row_id is not None:
            doc = messages.find_one({"_id": row_id})
            if doc:
                return dict(doc)
        chat_id = payload.get("chat_id")
        message_id = payload.get("message_id")
        if chat_id is not None and message_id is not None:
            doc = messages.find_one({"chat_id": chat_id, "message_id": message_id})
            if doc:
                return dict(doc)
        return None


def _citation_label(
    payload: dict[str, Any],
    *,
    source_type: str,
    source_id: str,
) -> str:
    chat_id = payload.get("chat_id")
    message_id = payload.get("message_id")
    row_id = payload.get("message_row_id")
    if chat_id is not None and message_id is not None:
        return f"chat:{chat_id}/msg:{message_id}"
    if row_id is not None:
        return f"message_row:{row_id}"
    return f"{source_type}:{source_id}"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    return str(value)
