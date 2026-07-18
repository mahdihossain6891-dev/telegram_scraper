"""Tests for auto_update.py."""

from __future__ import annotations

from unittest.mock import patch

from auto_update import AutoUpdateConfig, load_auto_update_config


@patch("auto_update.dotenv_values", return_value={})
@patch.dict(
    "os.environ",
    {
        "AUTO_UPDATE_SCRAPE_TARGET": "5",
        "AUTO_UPDATE_INTERVAL_MINUTES": "2",
        "AUTO_UPDATE_BOT_POST": "true",
        "AUTO_UPDATE_GIT_PUSH": "1",
    },
    clear=False,
)
def test_load_auto_update_config(_mock_values) -> None:
    config = load_auto_update_config()
    assert config.scrape_target == "5"
    assert config.interval_seconds == 120
    assert config.post_bot_messages is True
    assert config.git_push is True
    assert isinstance(config, AutoUpdateConfig)
