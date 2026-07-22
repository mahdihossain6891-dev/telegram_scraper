"""Tests for dashboard .env settings helpers."""

from __future__ import annotations

from pathlib import Path

import env_settings as module


def test_update_env_settings_writes_telegram_and_ai_keys(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TELEGRAM_API_ID=\nTELEGRAM_API_HASH=\n", encoding="utf-8")
    monkeypatch.setattr(module, "ENV_PATH", env_file)
    monkeypatch.setattr(module, "ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    snapshot = module.update_env_settings(
        {
            "TELEGRAM_API_ID": "99887766",
            "TELEGRAM_API_HASH": "abc123secret",
            "AI_ENABLED": "true",
            "AI_CHAT_PROVIDER": "openrouter",
            "AI_API_KEY": "sk-or-test-key",
        }
    )

    text = env_file.read_text(encoding="utf-8")
    assert "TELEGRAM_API_ID=99887766" in text
    assert "TELEGRAM_API_HASH=abc123secret" in text
    assert "AI_ENABLED=true" in text
    assert "OPENROUTER_API_KEY=sk-or-test-key" in text
    assert snapshot.configured["TELEGRAM_API_HASH"] is True
    assert snapshot.values["TELEGRAM_API_HASH"] == ""


def test_secret_left_blank_is_not_overwritten(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AI_API_KEY=keep-me\n", encoding="utf-8")
    monkeypatch.setattr(module, "ENV_PATH", env_file)
    monkeypatch.setattr(module, "ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    module.update_env_settings({"AI_API_KEY": "", "AI_ENABLED": "true"})
    text = env_file.read_text(encoding="utf-8")
    assert "AI_API_KEY=keep-me" in text
    assert "AI_ENABLED=true" in text
