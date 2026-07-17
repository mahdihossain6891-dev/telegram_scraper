"""Tests for entity extraction module."""

from __future__ import annotations

from sqlalchemy import func, select

from entity_extractor import (
    EmailExtractor,
    EntityMatch,
    HashtagExtractor,
    MentionExtractor,
    UrlExtractor,
    entity_already_stored,
    extract_entities,
    extract_for_all_messages,
    store_entities_for_message,
)
from models import Chat, ExtractedEntity, Message


class TestIndividualExtractors:
    """Tests for single entity extractors."""

    def test_url_extractor(self) -> None:
        text = "Visit https://example.com/path and http://test.org"
        matches = UrlExtractor().extract(text)
        assert len(matches) == 2
        assert matches[0].entity_type == "url"

    def test_email_extractor(self) -> None:
        matches = EmailExtractor().extract("Contact analyst@example.com today")
        assert len(matches) == 1
        assert matches[0].entity_value == "analyst@example.com"

    def test_hashtag_extractor(self) -> None:
        matches = HashtagExtractor().extract("Tracking #osint and #telegram")
        assert len(matches) == 2

    def test_mention_extractor(self) -> None:
        matches = MentionExtractor().extract("Ping @alice and @bob_smith")
        assert len(matches) == 2
        assert matches[0].entity_value == "@alice"


class TestExtractEntities:
    """Tests for combined extraction."""

    def test_extracts_multiple_entity_types(self) -> None:
        text = (
            "See https://bad.example/contact or email ops@bad.example "
            "tag #alert mention @source phone +1 555 123 4567"
        )
        matches = extract_entities(text)
        types = {match.entity_type for match in matches}
        assert "url" in types
        assert "email" in types
        assert "hashtag" in types
        assert "mention" in types
        assert "phone" in types
        assert "domain" in types

    def test_deduplicates_repeated_values(self) -> None:
        text = "https://example.com and https://example.com again"
        matches = extract_entities(text)
        urls = [m for m in matches if m.entity_type == "url"]
        assert len(urls) == 1

    def test_empty_text_returns_empty(self) -> None:
        assert extract_entities("") == []
        assert extract_entities(None) == []


class TestStoreEntities:
    """Tests for database persistence."""

    def _seed_message(self, db_settings, text: str) -> tuple:
        settings, db_module = db_settings
        chat = Chat(id=9001, title="Extract Chat", chat_type="channel")
        with db_module.get_session(settings) as session:
            session.add(chat)
            session.flush()
            message = Message(message_id=1, chat_id=9001, text=text)
            session.add(message)
            session.flush()
            message_id = message.id
        return settings, db_module, message_id

    def test_store_entities_for_message(self, db_settings) -> None:
        settings, db_module, message_id = self._seed_message(
            db_settings,
            "Visit https://example.com and #osint",
        )

        with db_module.get_session(settings) as session:
            stored, skipped = store_entities_for_message(
                session,
                message_id,
                "Visit https://example.com and #osint",
            )
            assert stored >= 2
            assert skipped == 0

        with db_module.get_session(settings) as session:
            count = session.scalar(select(func.count()).select_from(ExtractedEntity))
            assert count >= 2

    def test_skips_duplicate_entities(self, db_settings) -> None:
        settings, db_module, message_id = self._seed_message(
            db_settings,
            "Email test@example.com",
        )

        with db_module.get_session(settings) as session:
            first_stored, _ = store_entities_for_message(session, message_id, "Email test@example.com")
            second_stored, second_skipped = store_entities_for_message(
                session,
                message_id,
                "Email test@example.com",
            )
            assert first_stored >= 1
            assert second_stored == 0
            assert second_skipped >= 1
            assert entity_already_stored(session, message_id, "email", "test@example.com")

    def test_extract_for_all_messages(self, db_settings) -> None:
        settings, db_module = db_settings
        with db_module.get_session(settings) as session:
            session.add(Chat(id=9002, title="Batch Chat", chat_type="group"))
            session.flush()
            session.add(
                Message(
                    message_id=10,
                    chat_id=9002,
                    text="Link https://batch.example #review",
                )
            )

        result = extract_for_all_messages(settings)
        assert result.messages_processed == 1
        assert result.entities_stored >= 2
