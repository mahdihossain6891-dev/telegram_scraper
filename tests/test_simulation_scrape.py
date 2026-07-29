"""Tests for AI simulation dummy scrape into isolated MongoDB."""

from __future__ import annotations

from data_providers.router import end_simulation_mode, get_data_provider, start_simulation_mode
from data_providers.state import reset_to_live
from database import clear_simulation_database, database_available, get_simulation_database_name
from scrape_jobs.simulation_runner import run_simulation_scrape
from scrape_jobs.store import ScrapeJobStore
from simulator.generation.ai_content import generate_ai_simulation_messages


def test_generate_simulation_messages_has_keywords() -> None:
    drafts = generate_ai_simulation_messages(scenario="narcotics", count=12, seed=7)
    assert len(drafts) >= 6
    assert all(draft.text for draft in drafts)
    assert all(draft.timestamp for draft in drafts)
    assert any(d.chat_type == "private chat" for d in drafts)
    assert any(d.media_type or d.reply_to_message_id or d.views for d in drafts)


def test_simulation_scrape_writes_isolated_database() -> None:
    from config import load_settings

    settings = load_settings()
    if not database_available(settings):
        return

    reset_to_live()
    clear_simulation_database(settings)
    store = ScrapeJobStore()
    store.try_begin()
    result = run_simulation_scrape(settings, store, scenario="narcotics", limit=12)
    assert result.threats_detected > 0
    assert result.messages_analyzed >= result.threats_detected

    sim_db = get_simulation_database_name()
    provider = get_data_provider()
    start_simulation_mode(scenario="narcotics", auto_start=False, config={"bootstrap_ticks": 0})
    provider = get_data_provider()
    payload = provider.get_export_payload()
    assert payload.get("simulation", {}).get("database") == sim_db
    assert int(payload.get("counts", {}).get("messages") or 0) > 0

    end_simulation_mode()
    reset_to_live()
