"""Tests for data cleanup module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from clear_data import clear_env_credentials, clear_runtime_files, remove_private_chats, run_clear
from models import Chat, ExtractedEntity, Message, User


def _seed_mixed_chats(db_settings) -> tuple:
    settings, db_module = db_settings
    base = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

    with db_module.get_session(settings) as session:
        private_chat = Chat(id=501, title="Alice", chat_type="private chat")
        channel = Chat(id=-100999, title="Public Channel", chat_type="channel")
        sender = User(id=777, username="alice", first_name="Alice")
        session.add_all([private_chat, channel, sender])
        session.flush()

        private_message = Message(
            message_id=1,
            chat_id=501,
            sender_id=777,
            timestamp=base,
            text="private cocaine mention",
        )
        channel_message = Message(
            message_id=2,
            chat_id=-100999,
            sender_id=777,
            timestamp=base,
            text="public ghost gun mention",
        )
        session.add_all([private_message, channel_message])
        session.flush()
        session.add_all(
            [
                ExtractedEntity(
                    message_row_id=private_message.id,
                    entity_type="narcotics",
                    entity_value="cocaine",
                ),
                ExtractedEntity(
                    message_row_id=channel_message.id,
                    entity_type="firearms",
                    entity_value="ghost gun",
                ),
            ]
        )

    return settings, db_module


class TestRemovePrivateChats:
    """Tests for private chat cleanup."""

    def test_removes_only_private_chats(self, db_settings) -> None:
        settings, db_module = _seed_mixed_chats(db_settings)
        removed_chats, removed_messages, removed_entities = remove_private_chats(settings)

        assert removed_chats == 1
        assert removed_messages == 1
        assert removed_entities == 1

        with db_module.get_session(settings) as session:
            assert session.scalar(select(func.count()).select_from(Chat)) == 1
            assert session.scalar(select(func.count()).select_from(Message)) == 1
            remaining = session.scalar(select(Chat))
            assert remaining is not None
            assert remaining.chat_type == "channel"

    def test_no_private_chats_is_noop(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.add(Chat(id=-1001, title="Only Channel", chat_type="channel"))

        removed_chats, removed_messages, removed_entities = remove_private_chats(settings)
        assert removed_chats == 0
        assert removed_messages == 0
        assert removed_entities == 0


class TestClearRuntimeFiles:
    """Tests for runtime file cleanup."""

    def test_deletes_session_db_logs_and_exports(self, db_settings, tmp_path) -> None:
        settings, _db_module = db_settings
        session_file = settings.session_path.with_suffix(".session")
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text("session", encoding="utf-8")
        settings.database_path.write_text("db", encoding="utf-8")
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        settings.log_file.write_text("log", encoding="utf-8")
        settings.exports_dir.mkdir(parents=True, exist_ok=True)
        (settings.exports_dir / "messages.csv").write_text("csv", encoding="utf-8")

        removed = clear_runtime_files(settings)

        assert not session_file.is_file()
        assert not settings.database_path.is_file()
        assert not settings.log_file.is_file()
        assert not (settings.exports_dir / "messages.csv").is_file()
        assert len(removed) >= 4


class TestClearEnvCredentials:
    """Tests for .env credential cleanup."""

    def test_clears_telegram_keys(self, tmp_path) -> None:
        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "TELEGRAM_API_ID=12345",
                    "TELEGRAM_API_HASH=secret_hash",
                    "TELEGRAM_PHONE=+10000000000",
                    "LOG_LEVEL=INFO",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        class FakeSettings:
            project_root = tmp_path

        assert clear_env_credentials(FakeSettings()) is True
        content = env_path.read_text(encoding="utf-8")
        assert "TELEGRAM_API_ID=" in content
        assert "12345" not in content
        assert "secret_hash" not in content
        assert "+10000000000" not in content
        assert "LOG_LEVEL=INFO" in content


class TestRunClear:
    """Tests for combined cleanup."""

    def test_run_clear_all(self, db_settings, tmp_path) -> None:
        settings, _db_module = _seed_mixed_chats(db_settings)
        settings.session_path.with_suffix(".session").write_text("session", encoding="utf-8")
        env_path = settings.project_root / ".env"
        env_path.write_text(
            "TELEGRAM_API_ID=999\nTELEGRAM_API_HASH=hash\nTELEGRAM_PHONE=+1\n",
            encoding="utf-8",
        )

        result = run_clear(settings, private_chats=True, runtime=True)

        assert result.private_chats_removed == 1
        assert result.messages_removed == 1
        assert result.credentials_cleared is True
        assert len(result.files_removed) >= 1
        assert not settings.session_path.with_suffix(".session").is_file()
        assert not settings.database_path.is_file()
        assert "TELEGRAM_API_ID=" in env_path.read_text(encoding="utf-8")
        assert "999" not in env_path.read_text(encoding="utf-8")
