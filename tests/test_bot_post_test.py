"""Tests for bot_post_test.py."""

from __future__ import annotations

import json
from unittest.mock import patch

from bot_post_test import (
    BotPostConfig,
    DEFAULT_TEST_MESSAGES,
    load_bot_post_config,
    parse_args,
    post_test_messages,
    select_messages,
    send_channel_message,
)


def test_select_messages_default_first_message() -> None:
    args = parse_args([])
    assert select_messages(args) == (DEFAULT_TEST_MESSAGES[0],)


def test_select_messages_all() -> None:
    args = parse_args(["--all"])
    assert select_messages(args) == DEFAULT_TEST_MESSAGES


def test_select_messages_custom() -> None:
    args = parse_args(["--message", "[TEST] custom cocaine mention"])
    assert select_messages(args) == ("[TEST] custom cocaine mention",)


@patch("bot_post_test.dotenv_values", return_value={})
@patch.dict(
    "os.environ",
    {
        "TELEGRAM_BOT_TOKEN": "123:ABC",
        "TEST_CHANNEL_USERNAME": "https://t.me/osint_test_lab",
    },
    clear=False,
)
def test_load_bot_post_config_normalizes_channel(_mock_values) -> None:
    config = load_bot_post_config()
    assert config.bot_token == "123:ABC"
    assert config.channel == "@osint_test_lab"


@patch("bot_post_test.send_channel_message")
def test_post_test_messages(mock_send) -> None:
    mock_send.side_effect = [
        type("Result", (), {"message_text": "a", "message_id": 1, "ok": True, "error": None})(),
        type("Result", (), {"message_text": "b", "message_id": 2, "ok": True, "error": None})(),
    ]
    config = BotPostConfig(bot_token="123:ABC", channel="@lab")
    results = post_test_messages(config, ("a", "b"))
    assert len(results) == 2
    assert mock_send.call_count == 2


@patch("bot_post_test.urllib.request.urlopen")
def test_send_channel_message_success(mock_urlopen) -> None:
    payload = {"ok": True, "result": {"message_id": 99}}
    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

    result = send_channel_message(BotPostConfig("token", "@lab"), "hello")
    assert result.ok is True
    assert result.message_id == 99
