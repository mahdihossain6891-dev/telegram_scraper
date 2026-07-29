"""Tests for personnel activity rollups."""

from __future__ import annotations

from datetime import datetime, timezone

from models import Chat, ExtractedEntity, Message, User
from personnel import (
    get_personnel_detail,
    list_personnel,
    record_user_activity,
    rebuild_user_activity,
)


def test_record_user_activity_increments(db_settings) -> None:
    settings, db_module = db_settings
    with db_module.get_session(settings) as session:
        session.upsert_user(User(id=42, username="alice", first_name="Alice"))
        session.upsert_chat(Chat(id=-100, title="Lab", chat_type="channel"))
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record_user_activity(
            session,
            user_id=42,
            chat_id=-100,
            timestamp=ts,
            keywords=["cocaine", "fentanyl"],
            categories=["narcotics"],
            username="alice",
            first_name="Alice",
        )
        record_user_activity(
            session,
            user_id=42,
            chat_id=-100,
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
            keywords=["cocaine"],
            categories=["narcotics"],
            username="alice",
            first_name="Alice",
        )
        doc = session.user_activity.find_one({"_id": 42})
        assert doc is not None
        assert doc["message_count"] == 2
        assert doc["suspicious_count"] == 2
        assert doc["keywords"]["cocaine"] == 2
        assert doc["keywords"]["fentanyl"] == 1
        assert -100 in doc["chat_ids"]


def test_list_and_detail_personnel(db_settings) -> None:
    settings, db_module = db_settings
    with db_module.get_session(settings) as session:
        session.upsert_user(User(id=7, username="bob", first_name="Bob"))
        session.upsert_chat(Chat(id=-200, title="Ops", chat_type="channel"))
        msg = session.insert_message(
            Message(
                message_id=1,
                chat_id=-200,
                sender_id=7,
                timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
                text="ghost gun for sale",
            )
        )
        session.insert_entity(
            ExtractedEntity(
                message_row_id=msg.id or 0,
                entity_type="firearms",
                entity_value="ghost gun",
            )
        )
        rebuild_user_activity(session)
        rows = list_personnel(session, sort_by="suspicious_count")
        assert len(rows) == 1
        assert rows[0]["user_id"] == 7
        assert rows[0]["suspicious_count"] == 1
        detail = get_personnel_detail(session, 7)
        assert detail is not None
        assert detail["user"]["username"] == "bob"
        assert len(detail["messages"]) == 1
        assert "ghost gun" in detail["messages"][0]["keywords"]
