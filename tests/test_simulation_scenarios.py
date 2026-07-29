"""Tests for multi-select console simulation scenarios."""

from __future__ import annotations

from keyword_filter import scan_message_text
from simulator.generation.ai_content import generate_ai_simulation_messages
from simulator.generation.scenarios import (
    format_console_scenarios,
    parse_console_scenarios,
    scenario_focus_phrase,
)


def test_parse_console_scenarios_multi() -> None:
    assert parse_console_scenarios("narcotics,firearms") == ["narcotics", "firearms"]
    assert parse_console_scenarios("firearms;narcotics;firearms") == ["firearms", "narcotics"]
    assert parse_console_scenarios("invalid") == ["narcotics"]
    assert format_console_scenarios(["human_trafficking", "narcotics"]) == "human_trafficking,narcotics"


def test_scenario_focus_phrase_multi() -> None:
    phrase = scenario_focus_phrase(["narcotics", "firearms", "human_trafficking"])
    assert "narcotics" in phrase
    assert "firearms" in phrase
    assert "human trafficking" in phrase


def test_generate_messages_mixes_categories() -> None:
    drafts = generate_ai_simulation_messages(
        scenario="narcotics,firearms,human_trafficking",
        count=24,
        seed=99,
    )
    assert len(drafts) >= 12
    categories: set[str] = set()
    for draft in drafts:
        scan = scan_message_text(draft.text)
        categories.update(scan.categories)
    assert len(categories) >= 2
