"""Session history store for the Investigation Assistant.

Sessions live in ``ai_sessions`` only — never mixed into messages /
user_activity / behavioral_analytics / extracted_entities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database as MongoDatabase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SessionStore:
    """Persist multi-turn assistant conversations separately from intel data."""

    def __init__(
        self,
        db: MongoDatabase | None = None,
        *,
        collection_name: str = "ai_sessions",
        max_turns: int = 8,
    ) -> None:
        self.db = db
        self.collection_name = collection_name
        self.max_turns = max(1, int(max_turns))
        self._memory: dict[str, dict[str, Any]] = {}
        if db is not None:
            self.collection = db[collection_name]
        else:
            self.collection = None

    def ensure_indexes(self) -> None:
        if self.collection is None:
            return
        self.collection.create_index([("updated_at", -1)], name="ix_ai_sessions_updated")
        self.collection.create_index(
            [("subject.user_id", 1)], name="ix_ai_sessions_subject_user"
        )
        self.collection.create_index([("status", 1)], name="ix_ai_sessions_status")

    def create(
        self,
        *,
        subject: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _utcnow()
        doc = {
            "_id": str(uuid4()),
            "subject": dict(subject or {}),
            "messages": [],
            "metadata": dict(metadata or {}),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        if self.collection is not None:
            self.collection.insert_one(doc)
        else:
            self._memory[doc["_id"]] = doc
        return dict(doc)

    def get(self, session_id: str) -> dict[str, Any] | None:
        if self.collection is not None:
            doc = self.collection.find_one({"_id": session_id})
            return dict(doc) if doc else None
        doc = self._memory.get(session_id)
        return dict(doc) if doc else None

    def get_or_create(
        self,
        session_id: str | None = None,
        *,
        subject: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if session_id:
            existing = self.get(session_id)
            if existing:
                # Soft-dismissed sessions are not reused — start a fresh active one.
                if str(existing.get("status") or "active") == "dismissed":
                    return self.create(subject=subject)
                if subject:
                    self.update_subject(session_id, subject)
                    refreshed = self.get(session_id)
                    return refreshed or existing
                return existing
        return self.create(subject=subject)

    def set_status(self, session_id: str, status: str) -> dict[str, Any] | None:
        """Soft-update session status (``active`` | ``dismissed``). Never deletes."""
        normalized = (status or "").strip().lower()
        if normalized not in {"active", "dismissed"}:
            raise ValueError("status must be 'active' or 'dismissed'")
        now = _utcnow()
        fields: dict[str, Any] = {"status": normalized, "updated_at": now}
        if normalized == "dismissed":
            fields["dismissed_at"] = now
        else:
            fields["dismissed_at"] = None

        if self.collection is not None:
            doc = self.collection.find_one_and_update(
                {"_id": session_id},
                {"$set": fields},
                return_document=ReturnDocument.AFTER,
            )
            return dict(doc) if doc else None

        doc = self._memory.get(session_id)
        if not doc:
            return None
        doc.update(fields)
        return dict(doc)

    def update_subject(self, session_id: str, subject: dict[str, Any]) -> None:
        now = _utcnow()
        if self.collection is not None:
            self.collection.update_one(
                {"_id": session_id},
                {"$set": {"subject": dict(subject), "updated_at": now}},
            )
            return
        doc = self._memory.get(session_id)
        if doc:
            doc["subject"] = dict(subject)
            doc["updated_at"] = now

    def append_turn(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        intent: str | None = None,
        confidence: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        turn = {
            "role": role,
            "content": content,
            "citations": list(citations or []),
            "intent": intent,
            "confidence": confidence,
            "metadata": dict(metadata or {}),
            "timestamp": _utcnow().isoformat(),
        }
        if self.collection is not None:
            doc = self.collection.find_one_and_update(
                {"_id": session_id},
                {
                    "$push": {
                        "messages": {
                            "$each": [turn],
                            "$slice": -self.max_turns * 2,
                        }
                    },
                    "$set": {"updated_at": _utcnow()},
                },
                return_document=ReturnDocument.AFTER,
            )
            return dict(doc) if doc else None

        doc = self._memory.get(session_id)
        if not doc:
            return None
        messages = list(doc.get("messages") or [])
        messages.append(turn)
        doc["messages"] = messages[-(self.max_turns * 2) :]
        doc["updated_at"] = _utcnow()
        return dict(doc)

    def format_history(self, session: dict[str, Any], *, max_turns: int | None = None) -> str:
        """Render recent turns as plain text for the system prompt (not evidence)."""
        limit = max_turns or self.max_turns
        messages = list(session.get("messages") or [])[-limit * 2 :]
        if not messages:
            subject = session.get("subject") or {}
            if subject:
                return f"Subject in focus: {subject}"
            return "(No prior turns in this session.)"
        lines: list[str] = []
        subject = session.get("subject") or {}
        if subject:
            lines.append(f"Subject in focus: {subject}")
        for msg in messages:
            role = str(msg.get("role") or "?").upper()
            content = str(msg.get("content") or "").strip()
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
