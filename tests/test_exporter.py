"""Tests for data export module."""

from __future__ import annotations

import csv
import json

import pytest

from exporter import DataExporter, run_export
from models import Chat, ExtractedEntity, Message, User
from tests.test_analytics import _seed_analytics_data


class TestDataExporter:
    """Tests for CSV and JSON export."""

    def test_export_all_writes_csv_and_json(self, db_settings, tmp_path) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        exports_dir = tmp_path / "exports"

        with db_module.get_session(settings) as session:
            result = DataExporter(session).export_all(exports_dir)

        assert result.chat_count == 2
        assert result.user_count == 1
        assert result.message_count == 3
        assert result.entity_count == 10
        assert result.json_file.is_file()
        assert all(path.is_file() for path in result.csv_files)

    def test_messages_csv_content(self, db_settings, tmp_path) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        exports_dir = tmp_path / "exports"

        with db_module.get_session(settings) as session:
            DataExporter(session).export_all(exports_dir)

        with (exports_dir / "messages.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) == 3
        assert rows[0]["message_id"] == "1"
        assert "cocaine shipment" in rows[0]["text"]

    def test_json_export_structure(self, db_settings, tmp_path) -> None:
        settings, db_module = _seed_analytics_data(db_settings)
        exports_dir = tmp_path / "exports"

        with db_module.get_session(settings) as session:
            DataExporter(session).export_all(exports_dir)

        payload = json.loads((exports_dir / "export.json").read_text(encoding="utf-8"))
        assert payload["counts"]["messages"] == 3
        assert len(payload["entities"]) == 10
        assert payload["messages"][0]["chat_id"] == 100

    def test_export_empty_database(self, db_settings, tmp_path) -> None:
        settings, db_module = db_settings
        exports_dir = tmp_path / "exports"

        with db_module.get_session(settings) as session:
            result = DataExporter(session).export_all(exports_dir)

        assert result.message_count == 0
        assert result.json_file.is_file()
        payload = json.loads(result.json_file.read_text(encoding="utf-8"))
        assert payload["messages"] == []

    def test_run_export_integration(self, db_settings, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        import importlib

        import config as config_module

        settings, _db_module = _seed_analytics_data(db_settings)
        exports_dir = tmp_path / "exports"
        monkeypatch.setenv("EXPORTS_DIR", str(exports_dir))
        importlib.reload(config_module)
        settings = config_module.load_settings()

        result = run_export(settings)
        assert result.message_count == 3
        assert (exports_dir / "export.json").is_file()
