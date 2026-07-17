"""Tests for dashboard helper functions."""

from __future__ import annotations

from datetime import datetime, timezone

from analytics import AnalyticsEngine
from dashboard import (
    database_available,
    get_chat_table_rows,
    get_entity_table_rows,
    get_overview_metrics,
    list_entity_types,
    list_export_files,
    ranked_counts_as_rows,
    search_hits_as_rows,
)
from models import Chat, ExtractedEntity, Message, User


def _seed_dashboard_data(db_settings) -> tuple:
    settings, db_module = db_settings
    base = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    with db_module.get_session(settings) as session:
        channel = Chat(id=100, title="Alpha Channel", chat_type="channel")
        private = Chat(id=200, title="Private Person", chat_type="private chat")
        sender = User(id=300, username="alice", first_name="Alice")
        session.add_all([channel, private, sender])
        session.flush()

        message = Message(
            message_id=1,
            chat_id=100,
            sender_id=300,
            timestamp=base,
            text="ghost gun shipment https://alpha.example #alert",
        )
        private_message = Message(
            message_id=2,
            chat_id=200,
            sender_id=300,
            timestamp=base,
            text="private note about meth",
        )
        session.add_all([message, private_message])
        session.flush()

        session.add_all(
            [
                ExtractedEntity(
                    message_row_id=message.id,
                    entity_type="firearms",
                    entity_value="ghost gun",
                ),
                ExtractedEntity(
                    message_row_id=message.id,
                    entity_type="domain",
                    entity_value="alpha.example",
                ),
                ExtractedEntity(
                    message_row_id=private_message.id,
                    entity_type="narcotics",
                    entity_value="meth",
                ),
            ]
        )

    return settings, db_module


class TestDashboardHelpers:
    """Tests for dashboard data helpers."""

    def test_database_available(self, db_settings) -> None:
        settings, _db_module = _seed_dashboard_data(db_settings)
        assert database_available(settings) is True

    def test_overview_metrics(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            summary = AnalyticsEngine(session).build_summary()
            metrics = get_overview_metrics(session, summary)

        assert metrics.total_messages == 2
        assert metrics.total_chats == 2
        assert metrics.total_entities == 3
        assert metrics.private_chat_count == 1
        assert metrics.keyword_flag_count == 2

    def test_get_chat_table_rows_hides_private_by_default(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_chat_table_rows(session)

        assert len(rows) == 1
        assert rows[0]["title"] == "Alpha Channel"
        assert rows[0]["message_count"] == 1

    def test_get_chat_table_rows_can_include_private(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_chat_table_rows(session, include_private=True)

        assert len(rows) == 2

    def test_list_entity_types(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            entity_types = list_entity_types(session)

        assert "domain" in entity_types
        assert "firearms" in entity_types

    def test_get_entity_table_rows_filters_by_type(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_entity_table_rows(session, entity_type="domain")

        assert len(rows) == 1
        assert rows[0]["entity_value"] == "alpha.example"

    def test_search_hits_as_rows(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            hits = AnalyticsEngine(session).search_messages("ghost gun")

        rows = search_hits_as_rows(hits)
        assert len(rows) == 1
        assert "ghost gun" in rows[0]["text"]

    def test_ranked_counts_as_rows(self) -> None:
        from analytics import RankedCount

        rows = ranked_counts_as_rows((RankedCount(label="Alpha", count=3, detail="100"),))
        assert rows == [{"label": "Alpha", "count": 3, "detail": "100"}]

    def test_list_export_files(self, tmp_path) -> None:
        exports_dir = tmp_path / "exports"
        exports_dir.mkdir()
        (exports_dir / "messages.csv").write_text("id\n1\n", encoding="utf-8")
        (exports_dir / "export.json").write_text("{}", encoding="utf-8")

        files = list_export_files(exports_dir)
        assert [path.name for path in files] == ["export.json", "messages.csv"]
