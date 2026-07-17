"""Tests for export_dashboard.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from export_dashboard import ExportDashboardData, find_export_file, load_export_dashboard


@pytest.fixture
def sample_export_path() -> Path:
    return Path(__file__).resolve().parents[1] / "demo" / "export.sample.json"


def test_find_export_file_uses_demo_sample(db_settings, sample_export_path) -> None:
    settings, _ = db_settings
    found = find_export_file(settings)
    assert found == sample_export_path


def test_load_export_dashboard_parses_sample(sample_export_path) -> None:
    data = load_export_dashboard(sample_export_path)

    assert isinstance(data, ExportDashboardData)
    assert data.exported_at == "2026-01-01T00:00:00+00:00"
    assert len(data.messages) == 2
    assert len(data.chat_summaries) == 2
    assert len(data.entities) == 3
    assert len(data.category_counts) == 2

    categories = {row["category"] for row in data.category_counts}
    assert categories == {"narcotics", "firearms"}

    private_summary = next(row for row in data.chat_summaries if row["chat_id"] == 200)
    assert private_summary["firearms"] == 1
    assert private_summary["messages"] == 1


def test_load_export_dashboard_message_keywords(sample_export_path) -> None:
    data = load_export_dashboard(sample_export_path)
    dm = next(row for row in data.messages if row["chat_id"] == 200)
    assert "ghost gun" in dm["keywords"]
    assert "ghost gun" in dm["text"]
