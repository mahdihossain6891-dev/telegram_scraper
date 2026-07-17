"""Tests for database module and ORM models."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import database
from models import Chat, ExtractedEntity, Message, User


class TestInitDb:
    """Tests for database initialization."""

    def test_creates_all_tables(self, db_settings) -> None:
        settings, db_module = db_settings
        engine = db_module.get_engine(settings)
        table_names = set(inspect(engine).get_table_names())

        assert table_names == {"chats", "users", "messages", "extracted_entities"}

    def test_creates_database_file(self, db_settings) -> None:
        settings, _db_module = db_settings
        assert settings.database_path.is_file()


class TestSession:
    """Tests for session context manager."""

    def test_commits_on_success(self, db_settings) -> None:
        settings, db_module = db_settings

        with db_module.get_session(settings) as session:
            session.add(
                Chat(id=1001, title="Test Channel", username="testchannel", chat_type="channel")
            )

        with db_module.get_session(settings) as session:
            chat = session.get(Chat, 1001)
            assert chat is not None
            assert chat.title == "Test Channel"

    def test_rolls_back_on_error(self, db_settings) -> None:
        settings, db_module = db_settings

        with pytest.raises(RuntimeError):
            with db_module.get_session(settings) as session:
                session.add(Chat(id=2002, title="Rollback Chat", chat_type="group"))
                raise RuntimeError("force rollback")

        with db_module.get_session(settings) as session:
            assert session.get(Chat, 2002) is None


class TestModels:
    """Tests for ORM relationships and constraints."""

    def _sample_message(self, session: Session) -> Message:
        chat = Chat(id=3003, title="Intel Channel", username="intel", chat_type="channel")
        user = User(id=4004, username="analyst", first_name="Analyst")
        session.add_all([chat, user])
        session.flush()

        message = Message(
            message_id=555,
            chat_id=chat.id,
            sender_id=user.id,
            timestamp=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            text="Visit https://example.com #osint",
            media_type=None,
            reply_to_message_id=None,
            forward_from_chat_id=None,
            forward_from_message_id=None,
            views=42,
        )
        session.add(message)
        session.flush()
        return message

    def test_message_unique_per_chat(self, db_settings) -> None:
        settings, db_module = db_settings

        with pytest.raises(IntegrityError):
            with db_module.get_session(settings) as session:
                self._sample_message(session)
                session.add(
                    Message(
                        message_id=555,
                        chat_id=3003,
                        text="duplicate",
                    )
                )
                session.flush()

    def test_extracted_entity_links_to_message(self, db_settings) -> None:
        settings, db_module = db_settings

        with db_module.get_session(settings) as session:
            message = self._sample_message(session)
            session.add(
                ExtractedEntity(
                    message_row_id=message.id,
                    entity_type="url",
                    entity_value="https://example.com",
                    start_offset=6,
                    end_offset=25,
                )
            )

        with db_module.get_session(settings) as session:
            entity = session.scalar(select(ExtractedEntity))
            assert entity is not None
            assert entity.entity_type == "url"
            assert entity.message.text.startswith("Visit")

    def test_cascade_delete_chat_removes_messages(self, db_settings) -> None:
        settings, db_module = db_settings

        with db_module.get_session(settings) as session:
            message = self._sample_message(session)
            session.add(
                ExtractedEntity(
                    message_row_id=message.id,
                    entity_type="hashtag",
                    entity_value="#osint",
                )
            )

        with db_module.get_session(settings) as session:
            chat = session.get(Chat, 3003)
            session.delete(chat)

        with db_module.get_session(settings) as session:
            assert session.scalar(select(Message)) is None
            assert session.scalar(select(ExtractedEntity)) is None


class TestHelpers:
    """Tests for database helper functions."""

    def test_message_exists(self, db_settings) -> None:
        settings, db_module = db_settings

        with db_module.get_session(settings) as session:
            chat = Chat(id=5005, title="Helper Chat", chat_type="group")
            session.add(chat)
            session.flush()
            session.add(Message(message_id=99, chat_id=5005, text="hello"))

        with db_module.get_session(settings) as session:
            assert db_module.message_exists(session, 5005, 99) is True
            assert db_module.message_exists(session, 5005, 100) is False

    def test_get_chat_by_id(self, db_settings) -> None:
        settings, db_module = db_settings

        with db_module.get_session(settings) as session:
            session.add(Chat(id=6006, title="Lookup Chat", chat_type="supergroup"))

        with db_module.get_session(settings) as session:
            chat = db_module.get_chat_by_id(session, 6006)
            assert chat is not None
            assert chat.title == "Lookup Chat"
            assert db_module.get_chat_by_id(session, 9999) is None
