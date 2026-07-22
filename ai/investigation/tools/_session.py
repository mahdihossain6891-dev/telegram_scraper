"""Shared helpers for investigation tools."""

from __future__ import annotations

from typing import Any

from database import MongoSession


def as_mongo_session(db: Any) -> MongoSession | None:
    if db is None:
        return None
    if isinstance(db, MongoSession):
        return db
    return MongoSession(db)


def user_id_from_subject(subject: dict[str, Any] | None) -> int | None:
    subject = subject or {}
    uid = subject.get("user_id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None


def chat_id_from_subject(subject: dict[str, Any] | None) -> int | None:
    subject = subject or {}
    cid = subject.get("chat_id")
    if cid is None:
        return None
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None
