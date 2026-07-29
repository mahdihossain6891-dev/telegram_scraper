"""Tests for simulator keyword integration."""

from __future__ import annotations

import random

from simulator.keywords import enrich_text_with_keyword, scan_simulation_text, sample_keywords
from simulator.pipeline.context import ProcessingContext
from simulator.pipeline.stages import KeywordStage
from simulator.models import MessageEvent


def test_scan_simulation_text_matches_osint_keywords() -> None:
    keywords, categories = scan_simulation_text("Looking for cocaine delivery tonight")
    assert "cocaine" in keywords
    assert "narcotics" in categories


def test_keyword_stage_uses_production_keyword_lists() -> None:
    event = MessageEvent(
        message_id=1,
        sender_id="u1",
        chat_id="c1",
        text="Illegal guns for sale in the group",
        timestamp="2026-01-01T00:00:00",
    )
    ctx = ProcessingContext(event=event, session_id="s1", tick=1)
    ctx.normalized_text = event.text.lower()
    KeywordStage().process(ctx)
    assert ctx.keywords
    assert "firearms" in (ctx.metrics.get("keyword_categories") or [])


def test_enrich_text_injects_keyword() -> None:
    rng = random.Random(42)
    out = enrich_text_with_keyword("Hello there", ("methamphetamine",), rng, probability=1.0)
    assert "methamphetamine" in out.lower()
