"""Tests for DatabaseContext."""

from __future__ import annotations

from simulator.contexts.database import DatabaseContext
from simulator.enums import EnvironmentType


class TestDatabaseContext:
    def test_separate_database_strategy(self) -> None:
        ctx = DatabaseContext(
            environment=EnvironmentType.SIMULATION,
            database_name="telegram_scraper_simulation",
        )
        assert ctx.collection_name("messages") == "messages"
        collections = ctx.collections()
        assert "messages" in collections
        assert collections["messages"] == "messages"

    def test_prefix_strategy(self) -> None:
        ctx = DatabaseContext(
            environment=EnvironmentType.SIMULATION,
            database_name="shared_db",
            collection_strategy="collection_prefix",
            collection_prefix="sim_",
        )
        assert ctx.collection_name("messages") == "sim_messages"

    def test_to_dict_includes_namespace(self) -> None:
        ctx = DatabaseContext(
            environment=EnvironmentType.LIVE,
            database_name="telegram_scraper",
        )
        data = ctx.to_dict()
        assert data["database_name"] == "telegram_scraper"
        assert data["environment"] == "live"
