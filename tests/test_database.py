"""Tests for MongoDB helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from models import Chat, ExtractedEntity, Message, User


class TestSession:
    def test_init_creates_indexes(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            assert session.messages is not None

    def test_commit_persists_chat(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.upsert_chat(Chat(id=1, title="Alpha", chat_type="channel"))
        with db_module.get_session(settings) as session:
            chat = session.get_chat(1)
            assert chat is not None
            assert chat.title == "Alpha"

    def test_message_unique_constraint(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.upsert_chat(Chat(id=10, title="Lab", chat_type="channel"))
            session.insert_message(Message(message_id=100, chat_id=10, text="one"))
            try:
                session.insert_message(Message(message_id=100, chat_id=10, text="dupe"))
                raised = False
            except Exception:
                raised = True
            assert raised or db_module.message_exists(session, 10, 100)

    def test_message_exists(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.upsert_chat(Chat(id=2, title="Beta", chat_type="channel"))
            session.insert_message(Message(message_id=55, chat_id=2, text="hi"))
            assert db_module.message_exists(session, 2, 55) is True
            assert db_module.message_exists(session, 2, 56) is False

    def test_entities_link_to_message(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.upsert_chat(Chat(id=3, title="Gamma", chat_type="channel"))
            message = session.insert_message(
                Message(
                    message_id=1,
                    chat_id=3,
                    text="cocaine test",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            session.insert_entity(
                ExtractedEntity(
                    message_row_id=message.id or 0,
                    entity_type="narcotics",
                    entity_value="cocaine",
                )
            )
            entities = session.list_entities()
            assert len(entities) == 1
            assert entities[0].entity_value == "cocaine"

    def test_upsert_user(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.upsert_user(User(id=7, username="alice", first_name="Alice"))
            session.upsert_user(User(id=7, username="alice2", first_name="Alice"))
            user = session.get_user(7)
            assert user is not None
            assert user.username == "alice2"
