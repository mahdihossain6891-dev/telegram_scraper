"""Tests for message scraper module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select
from telethon.tl.types import Message as TelethonMessage
from telethon.tl.types import MessageFwdHeader, MessageReplyHeader, PeerChannel, User

from chat_discovery import DiscoveredChat
from keyword_filter import scan_message_text
from message_scraper import (
    MessageScrapeError,
    MessageScraper,
    parse_limit_input,
    parse_scrape_target,
    parse_telethon_message,
    store_parsed_message,
)
from models import Chat, ExtractedEntity, Message


def _run(coro):
    return asyncio.run(coro)


def _discovered_chat() -> DiscoveredChat:
    return DiscoveredChat(
        chat_id=-1001234567890,
        name="Intel Channel",
        chat_type="channel",
        index=1,
        username="intel",
    )


def _telethon_message(
    message_id: int = 101,
    *,
    text: str = "Hello world",
    reply_to: int | None = None,
    views: int | None = 10,
    with_forward: bool = False,
) -> TelethonMessage:
    message = TelethonMessage(
        id=message_id,
        peer_id=PeerChannel(channel_id=1234567890),
        date=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        message=text,
        views=views,
    )
    if reply_to is not None:
        message.reply_to = MessageReplyHeader(reply_to_msg_id=reply_to)
    if with_forward:
        message.forward = MessageFwdHeader(
            date=datetime(2026, 1, 14, 8, 0, tzinfo=timezone.utc),
            from_id=PeerChannel(channel_id=999),
            channel_post=55,
        )
    return message


class TestLimitValidation:
    """Tests for scrape limit validation."""

    def test_allowed_limits(self) -> None:
        assert parse_limit_input("100") == 100
        assert parse_limit_input("500") == 500
        assert parse_limit_input("1000") == 1000

    def test_invalid_limit_raises(self) -> None:
        with pytest.raises(MessageScrapeError, match="Limit must be one of"):
            parse_limit_input("250")


class TestParseScrapeTarget:
    """Tests for CLI scrape target parsing."""

    def test_parse_batch_all(self) -> None:
        assert parse_scrape_target("all") == ("batch", "all")

    def test_parse_batch_private(self) -> None:
        assert parse_scrape_target("all-private") == ("batch", "private")

    def test_parse_single_index(self) -> None:
        assert parse_scrape_target("3") == ("single", "3")


class TestParseTelethonMessage:
    """Tests for Telethon-to-database field mapping."""

    def test_maps_core_fields(self) -> None:
        sender = User(id=42, access_hash=0, first_name="Alice", username="alice")
        message = MagicMock()
        message.id = 77
        message.date = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        message.message = "Check https://example.com"
        message.media = None
        message.reply_to = MessageReplyHeader(reply_to_msg_id=12)
        message.forward = MessageFwdHeader(
            date=datetime(2026, 1, 14, 8, 0, tzinfo=timezone.utc),
            from_id=PeerChannel(channel_id=999),
            channel_post=55,
        )
        message.views = 99
        message.sender_id = 42
        message.sender = sender

        parsed = parse_telethon_message(message, chat_id=-1001234567890)

        assert parsed.message_id == 77
        assert parsed.chat_id == -1001234567890
        assert parsed.sender_id == 42
        assert parsed.text == "Check https://example.com"
        assert parsed.reply_to_message_id == 12
        assert parsed.views == 99
        assert parsed.forward_from_message_id == 55
        assert parsed.sender_username == "alice"
        assert parsed.sender_first_name == "Alice"


class TestStoreParsedMessage:
    """Tests for duplicate-safe database inserts."""

    def test_stores_new_message(self, db_settings) -> None:
        settings, db_module = db_settings
        chat = _discovered_chat()
        parsed = parse_telethon_message(
            _telethon_message(text="Report mentions cocaine shipment"),
            chat.chat_id,
        )
        keyword_scan = scan_message_text(parsed.text)

        with db_module.get_session(settings) as session:
            from message_scraper import ensure_chat_record

            ensure_chat_record(session, chat)
            assert store_parsed_message(session, parsed, keyword_scan) is True

        with db_module.get_session(settings) as session:
            assert session.scalar(select(func.count()).select_from(Message)) == 1
            assert session.scalar(select(func.count()).select_from(ExtractedEntity)) == 1
            row = session.scalar(select(Message))
            assert row is not None
            assert row.message_id == 101
            assert row.chat_id == chat.chat_id

    def test_skips_duplicate_message(self, db_settings) -> None:
        settings, db_module = db_settings
        chat = _discovered_chat()
        parsed = parse_telethon_message(
            _telethon_message(text="ghost gun discussion"),
            chat.chat_id,
        )
        keyword_scan = scan_message_text(parsed.text)

        with db_module.get_session(settings) as session:
            from message_scraper import ensure_chat_record

            ensure_chat_record(session, chat)
            assert store_parsed_message(session, parsed, keyword_scan) is True
            assert store_parsed_message(session, parsed, keyword_scan) is False

    def test_skips_message_without_keywords(self, db_settings) -> None:
        settings, db_module = db_settings
        chat = _discovered_chat()
        parsed = parse_telethon_message(_telethon_message(text="normal conversation"), chat.chat_id)
        keyword_scan = scan_message_text(parsed.text)

        with db_module.get_session(settings) as session:
            from message_scraper import ensure_chat_record

            ensure_chat_record(session, chat)
            assert store_parsed_message(session, parsed, keyword_scan) is False


class TestMessageScraper:
    """Tests for batch collection workflow."""

    def test_scrape_chat_respects_limit_and_batches(self, db_settings) -> None:
        settings, db_module = db_settings
        chat = _discovered_chat()
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=True)

        messages = [
            _telethon_message(message_id=1, text="regular update"),
            _telethon_message(message_id=2, text="possible cocaine route"),
            _telethon_message(message_id=3, text="sports news"),
            _telethon_message(message_id=4, text="ghost gun mention"),
            _telethon_message(message_id=5, text="weather report"),
        ]

        async def _iter_messages(_chat_id, limit=None):
            for message in messages[:limit]:
                yield message

        client.iter_messages = MagicMock(side_effect=_iter_messages)

        scraper = MessageScraper(client, settings, batch_size=2)
        result = _run(scraper.scrape_chat(chat, limit=100))

        assert result.processed == 5
        assert result.flagged_stored == 2
        assert result.skipped_no_keyword == 3
        assert result.skipped_duplicates == 0

        with db_module.get_session(settings) as session:
            assert session.get(Chat, chat.chat_id) is not None
            assert session.scalar(select(func.count()).select_from(Message)) == 2
            assert session.scalar(select(func.count()).select_from(ExtractedEntity)) >= 2

    def test_scrape_chat_skips_existing_messages(self, db_settings) -> None:
        settings, db_module = db_settings
        chat = _discovered_chat()

        with db_module.get_session(settings) as session:
            session.add(
                Chat(
                    id=chat.chat_id,
                    title=chat.name,
                    username=chat.username,
                    chat_type=chat.chat_type,
                )
            )
            session.add(
                Message(
                    message_id=1,
                    chat_id=chat.chat_id,
                    text="existing cocaine mention",
                )
            )

        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=True)

        async def _iter_messages(_chat_id, limit=None):
            yield _telethon_message(message_id=1, text="existing cocaine mention")
            yield _telethon_message(message_id=2, text="new ghost gun post")

        client.iter_messages = MagicMock(side_effect=_iter_messages)

        scraper = MessageScraper(client, settings, batch_size=10)
        result = _run(scraper.scrape_chat(chat, limit=100))

        assert result.processed == 2
        assert result.flagged_stored == 1
        assert result.skipped_duplicates == 1
        assert result.skipped_no_keyword == 0

    def test_scrape_chat_requires_authorization(self, db_settings) -> None:
        settings, _db_module = db_settings
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=False)

        scraper = MessageScraper(client, settings)
        with pytest.raises(MessageScrapeError, match="not authorized"):
            _run(scraper.scrape_chat(_discovered_chat(), limit=100))

    def test_scrape_chats_runs_each_chat(self, db_settings) -> None:
        settings, db_module = db_settings
        chats = [
            _discovered_chat(),
            DiscoveredChat(
                chat_id=-100999,
                name="Second Chat",
                chat_type="supergroup",
                index=2,
            ),
        ]
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=True)

        async def _iter_messages(_chat_id, limit=None):
            if _chat_id == chats[0].chat_id:
                yield _telethon_message(message_id=1, text="cocaine mention")
            else:
                yield _telethon_message(message_id=2, text="ghost gun mention")

        client.iter_messages = MagicMock(side_effect=_iter_messages)

        scraper = MessageScraper(client, settings, batch_size=10)
        result = _run(scraper.scrape_chats(chats, limit=100, scope="all"))

        assert result.chats_scanned == 2
        assert result.total_flagged_stored == 2
        with db_module.get_session(settings) as session:
            assert session.scalar(select(func.count()).select_from(Chat)) == 2

    def test_scrape_chats_continues_after_chat_error(self, db_settings) -> None:
        settings, db_module = db_settings
        chats = [
            _discovered_chat(),
            DiscoveredChat(
                chat_id=-100999,
                name="Broken Chat",
                chat_type="private chat",
                index=2,
            ),
        ]
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=True)

        call_count = {"value": 0}

        async def _iter_messages(_chat_id, limit=None):
            call_count["value"] += 1
            if _chat_id == chats[0].chat_id:
                yield _telethon_message(message_id=1, text="cocaine mention")
                return
            raise MessageScrapeError("Telegram blocked this chat")

        client.iter_messages = MagicMock(side_effect=_iter_messages)

        scraper = MessageScraper(client, settings, batch_size=10)
        result = _run(scraper.scrape_chats(chats, limit=100, scope="private"))

        assert result.chats_scanned == 2
        assert result.total_flagged_stored == 1
        assert result.chat_results[1].error is not None
