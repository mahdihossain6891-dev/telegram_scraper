"""Tests for dashboard helper functions."""

from __future__ import annotations

from datetime import datetime, timezone

from analytics import AnalyticsEngine
from dashboard import (
    DashboardFilters,
    database_available,
    dataframe_csv_bytes,
    default_filters,
    get_category_summary_rows,
    get_chat_table_rows,
    get_chat_type_breakdown,
    get_dashboard_insights,
    get_detailed_chat_summaries,
    get_entity_table_rows,
    get_message_rows,
    get_overview_metrics,
    get_stored_chat_options,
    get_top_keyword_term_rows,
    keyword_category_chart,
    list_entity_types,
    list_export_files,
    messages_per_chat_chart,
    ranked_counts_as_rows,
    search_hits_as_rows,
    timeline_from_message_rows,
    top_terms_from_entity_rows,
)
from models import Chat, ExtractedEntity, Message, User


def _seed_dashboard_data(db_settings) -> tuple:
    settings, db_module = db_settings
    base = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)

    with db_module.get_session(settings) as session:
        channel_a = Chat(id=100, title="Alpha Channel", chat_type="channel")
        channel_b = Chat(id=150, title="Beta Group", chat_type="supergroup")
        private = Chat(id=200, title="Private Person", chat_type="private chat")
        sender = User(id=300, username="alice", first_name="Alice")
        session.add_all([channel_a, channel_b, private, sender])
        session.flush()

        messages = [
            Message(
                message_id=1,
                chat_id=100,
                sender_id=300,
                timestamp=base,
                text="ghost gun shipment https://alpha.example #alert",
            ),
            Message(
                message_id=2,
                chat_id=150,
                sender_id=300,
                timestamp=base.replace(hour=12),
                text="cocaine shipment update",
            ),
            Message(
                message_id=3,
                chat_id=200,
                sender_id=300,
                timestamp=base,
                text="private note about meth",
            ),
        ]
        session.add_all(messages)
        session.flush()

        session.add_all(
            [
                ExtractedEntity(
                    message_row_id=messages[0].id,
                    entity_type="firearms",
                    entity_value="ghost gun",
                ),
                ExtractedEntity(
                    message_row_id=messages[0].id,
                    entity_type="domain",
                    entity_value="alpha.example",
                ),
                ExtractedEntity(
                    message_row_id=messages[1].id,
                    entity_type="narcotics",
                    entity_value="cocaine",
                ),
                ExtractedEntity(
                    message_row_id=messages[2].id,
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

        assert metrics.total_messages == 3
        assert metrics.total_chats == 3
        assert metrics.flagged_chats == 3
        assert metrics.total_entities == 4
        assert metrics.private_chat_count == 1
        assert metrics.keyword_flag_count == 3

    def test_get_stored_chat_options(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            options = get_stored_chat_options(session, include_private=False)

        assert len(options) == 2
        assert {opt.title for opt in options} == {"Alpha Channel", "Beta Group"}

    def test_get_detailed_chat_summaries(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_detailed_chat_summaries(session, default_filters())

        assert len(rows) == 3
        alpha = next(row for row in rows if row["title"] == "Alpha Channel")
        beta = next(row for row in rows if row["title"] == "Beta Group")
        assert alpha["messages"] == 1
        assert alpha["firearms"] == 1
        assert beta["narcotics"] == 1

    def test_get_chat_table_rows_hides_private_by_default(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_chat_table_rows(session, include_private=False)

        assert len(rows) == 2

    def test_get_message_rows_with_category_filter(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        filters = DashboardFilters(
            chat_ids=(),
            categories=("firearms",),
            include_private=False,
            chat_type=None,
            min_messages=0,
        )
        with db_module.get_session(settings) as session:
            rows = get_message_rows(session, filters)

        assert len(rows) == 1
        assert rows[0]["keywords"] == "ghost gun"

    def test_get_category_summary_rows(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_category_summary_rows(session, default_filters())

        categories = {row["category"] for row in rows}
        assert "firearms" in categories
        assert "narcotics" in categories

    def test_list_entity_types(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            entity_types = list_entity_types(session)

        assert "domain" in entity_types
        assert "firearms" in entity_types

    def test_get_entity_table_rows_filters_by_type(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_entity_table_rows(session, default_filters(), entity_type="domain")

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

    def test_dataframe_csv_bytes(self) -> None:
        payload = dataframe_csv_bytes([{"a": 1, "b": "x"}])
        assert b"a,b" in payload
        assert b"1,x" in payload

    def test_chart_helpers(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            chat_rows = get_detailed_chat_summaries(session, default_filters())
            category_rows = get_category_summary_rows(session, default_filters())

        chat_chart = messages_per_chat_chart(chat_rows)
        category_chart = keyword_category_chart(category_rows)
        assert chat_chart.data
        assert category_chart.data

    def test_get_top_keyword_term_rows(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_top_keyword_term_rows(session, default_filters(), limit=5)

        terms = {row["term"] for row in rows}
        assert "ghost gun" in terms
        assert "cocaine" in terms

    def test_get_chat_type_breakdown(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_chat_type_breakdown(session, default_filters())

        types = {row["chat_type"] for row in rows}
        assert "channel" in types
        assert "private chat" in types

    def test_get_dashboard_insights(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            insights = get_dashboard_insights(session, default_filters())

        assert insights.busiest_chat in {"Alpha Channel", "Beta Group", "Private Person"}
        assert insights.top_keyword in {"ghost gun", "cocaine", "meth"}
        assert insights.earliest_message

    def test_timeline_from_message_rows(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            rows = get_message_rows(session, default_filters(), limit=10)

        timeline = timeline_from_message_rows(rows)
        assert timeline
        assert timeline[0]["messages"] >= 1

    def test_top_terms_from_entity_rows(self, db_settings) -> None:
        settings, db_module = _seed_dashboard_data(db_settings)
        with db_module.get_session(settings) as session:
            entities = get_entity_table_rows(session, default_filters(), limit=10)

        terms = top_terms_from_entity_rows(entities, limit=5)
        assert any(row["term"] == "ghost gun" for row in terms)
