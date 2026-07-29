"""Tests for Telegram alert helpers."""

from __future__ import annotations

from telegram_alerts import (
    AlertConfig,
    AlertMessage,
    format_alert_digest,
    should_include_message,
)


def test_format_alert_digest_includes_preview() -> None:
    text = format_alert_digest(
        [
            AlertMessage(
                chat_name="Lab",
                message_id=1,
                sender="alice",
                text="cocaine shipment mentioned",
                categories=("narcotics",),
                keywords=("cocaine",),
                addresses=("phone: +1-555-014-8821", "wallet: 0xabc"),
            )
        ]
    )
    assert "OSINT alert" in text
    assert "Lab" in text
    assert "cocaine" in text
    assert "phone: +1-555-014-8821" in text


def test_should_include_message_when_address_present() -> None:
    cfg = AlertConfig(
        enabled=True,
        bot_token="x",
        chat_id="@x",
        on_scrape=True,
        multi_category_only=True,
        min_keywords=5,
        cooldown_seconds=0,
    )
    assert should_include_message(cfg, ["narcotics"], ["cocaine"], ("phone: +1",))


def test_should_include_respects_multi_category() -> None:
    cfg = AlertConfig(
        enabled=True,
        bot_token="x",
        chat_id="@x",
        on_scrape=True,
        multi_category_only=True,
        min_keywords=1,
        cooldown_seconds=0,
    )
    assert not should_include_message(cfg, ["narcotics"], ["cocaine"])
    assert should_include_message(cfg, ["narcotics", "firearms"], ["cocaine", "gun"])
