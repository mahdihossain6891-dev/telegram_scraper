"""Tests for analytics module."""

from __future__ import annotations

from datetime import datetime, timezone

from analytics import AnalyticsEngine, messages_per_day_chart, run_analytics, save_charts
from models import Chat, ExtractedEntity, Message, User


def _seed_analytics_data(db_settings) -> tuple:
    settings, db_module = db_settings
    base = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    with db_module.get_session(settings) as session:
        session.upsert_chat(Chat(id=100, title="Alpha Channel", chat_type="channel"))
        session.upsert_chat(Chat(id=200, title="Beta Group", chat_type="supergroup"))
        session.upsert_user(User(id=300, username="alice", first_name="Alice"))

        messages = [
            session.insert_message(
                Message(
                    message_id=1,
                    chat_id=100,
                    sender_id=300,
                    timestamp=base,
                    text="cocaine shipment via https://alpha.example contact ops@alpha.example #alert",
                )
            ),
            session.insert_message(
                Message(
                    message_id=2,
                    chat_id=100,
                    sender_id=300,
                    timestamp=base.replace(hour=14),
                    text="ghost gun discussion https://alpha.example again #alert",
                )
            ),
            session.insert_message(
                Message(
                    message_id=3,
                    chat_id=200,
                    sender_id=300,
                    timestamp=base.replace(day=16, hour=9),
                    text="human trafficking report https://beta.example #review",
                )
            ),
        ]

        entities = [
            ExtractedEntity(message_row_id=messages[0].id or 0, entity_type="narcotics", entity_value="cocaine"),
            ExtractedEntity(message_row_id=messages[0].id or 0, entity_type="domain", entity_value="alpha.example"),
            ExtractedEntity(message_row_id=messages[0].id or 0, entity_type="hashtag", entity_value="#alert"),
            ExtractedEntity(message_row_id=messages[0].id or 0, entity_type="email", entity_value="ops@alpha.example"),
            ExtractedEntity(message_row_id=messages[1].id or 0, entity_type="firearms", entity_value="ghost gun"),
            ExtractedEntity(message_row_id=messages[1].id or 0, entity_type="domain", entity_value="alpha.example"),
            ExtractedEntity(message_row_id=messages[1].id or 0, entity_type="hashtag", entity_value="#alert"),
            ExtractedEntity(message_row_id=messages[2].id or 0, entity_type="human_trafficking", entity_value="human trafficking"),
            ExtractedEntity(message_row_id=messages[2].id or 0, entity_type="domain", entity_value="beta.example"),
            ExtractedEntity(message_row_id=messages[2].id or 0, entity_type="hashtag", entity_value="#review"),
        ]
        for entity in entities:
            session.insert_entity(entity)

    return settings, db_module


class TestAnalyticsEngine:
    """Tests for analytics calculations."""

    def test_total_message_count(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            assert engine.total_message_count() == 3

    def test_top_chats_and_senders(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            top_chats = engine.top_chats()
            top_senders = engine.top_senders()
            assert top_chats[0].label == "Alpha Channel"
            assert top_chats[0].count == 2
            assert top_senders[0].count == 3

    def test_top_domains_and_hashtags(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            domains = engine.top_domains()
            hashtags = engine.top_hashtags()
            assert domains[0].label == "alpha.example"
            assert domains[0].count == 2
            assert any(item.label == "#alert" for item in hashtags)

    def test_messages_per_day_and_hour(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            per_day = engine.messages_per_day()
            per_hour = engine.messages_per_hour()
            assert len(per_day) == 2
            assert any(item.label.endswith("01-15") or "2026-01-15" in item.label for item in per_day)
            assert any(item.label.startswith("10:") for item in per_hour)

    def test_keyword_search(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            hits = engine.search_messages("ghost gun")
            assert len(hits) == 1
            assert hits[0].message_id == 2

    def test_word_frequency(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            engine = AnalyticsEngine(session)
            words = engine.word_frequency(limit=5)
            assert any(item.label == "alpha" or item.label == "https" for item in words) or len(words) > 0

    def test_build_summary(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            summary = AnalyticsEngine(session).build_summary()
            assert summary.total_messages == 3
            assert len(summary.top_domains) >= 1
            assert len(summary.keyword_flags) >= 1

    def test_messages_per_day_chart(self, db_settings) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            summary = AnalyticsEngine(session).build_summary()
        figure = messages_per_day_chart(summary)
        assert figure.data
        assert figure.layout.title.text == "Messages Per Day"

    def test_save_charts_writes_html(self, db_settings, tmp_path) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        with db_module.get_session(settings) as session:
            summary = AnalyticsEngine(session).build_summary()

        exports_dir = tmp_path / "exports"
        daily, hourly = save_charts(summary, exports_dir)
        assert daily.is_file()
        assert hourly.is_file()

    def test_run_analytics_with_empty_search(self, db_settings) -> None:
        settings, _db_module = _seed_analytics_data(db_settings)
        summary = run_analytics(settings, search_query=None, save_html_charts=False)
        assert summary.total_messages == 3
