"""Tests for simulation facade message ingestion."""

from __future__ import annotations

import re

from simulator.api.facade import SimulationConsoleFacade

_NON_LATIN = re.compile(r"[^\x00-\x7F]")


def test_ingest_runtime_dedupes_messages() -> None:
    facade = SimulationConsoleFacade()
    summary = facade.create_session(
        name="dedupe-test",
        config={"users": 6, "groups": 2, "max_ticks": 1, "max_messages_per_tick": 2},
    )
    sid = summary["session_id"]
    facade.tick(sid)
    record = facade._require_record(sid)
    count_after_first = len(record.messages)
    facade._ingest_runtime(record)
    assert len(record.messages) == count_after_first


def test_console_session_uses_english_only_generation() -> None:
    facade = SimulationConsoleFacade()
    summary = facade.create_session(name="english-only", config={"users": 12, "groups": 2})
    sid = summary["session_id"]
    record = facade._require_record(sid)
    dist = record.engine.generation_config.language_distribution
    assert dist == {"english": 1.0}
    assert record.engine._scenario_config.languages == ("english",)

    personas = facade.personas(sid, limit=50)
    assert personas
    assert all(persona.get("languages") == ["english"] for persona in personas)
    assert all(not _NON_LATIN.search(str(persona.get("display_name") or "")) for persona in personas)
