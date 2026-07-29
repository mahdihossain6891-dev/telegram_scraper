"""Tests for the risk scoring engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_scoring import classify_risk, score_chat, score_message, score_user


def test_classify_bands() -> None:
    assert classify_risk(0) == "Low"
    assert classify_risk(20) == "Low"
    assert classify_risk(21) == "Medium"
    assert classify_risk(41) == "High"
    assert classify_risk(71) == "Critical"
    assert classify_risk(100) == "Critical"


def test_message_keyword_weights() -> None:
    cocaine = score_message(keywords=["cocaine"], categories=["narcotics"])
    assert cocaine.score >= 35
    assert cocaine.level in {"Medium", "High", "Critical"}

    ak = score_message(keywords=["ak-47"], categories=["firearms"], text="AK-47 for sale")
    assert ak.score >= 40

    passport = score_message(
        keywords=["passport for sale"],
        categories=["human_trafficking"],
        text="passport for sale cheap",
    )
    assert passport.score >= 50


def test_user_behavior_bonuses() -> None:
    now = datetime.now(timezone.utc)
    assessment = score_user(
        message_count=5,
        chat_ids=[1, 2],
        keywords={"cocaine": 3},
        categories={"narcotics": 3, "firearms": 1},
        first_seen=now - timedelta(days=2),
    )
    assert assessment.score >= 35 + 20 + 30 + 15
    assert assessment.level == "Critical"


def test_chat_scoring() -> None:
    assessment = score_chat(
        message_count=12,
        sender_count=4,
        keywords={"fentanyl": 5},
        categories={"narcotics": 5},
    )
    assert assessment.score >= 40
    assert "high_volume" in ",".join(assessment.factors)
