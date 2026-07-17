"""Tests for environment validation helper."""

from __future__ import annotations

from check_env import validate_env_file


def test_validate_env_file_reports_missing_values(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TELEGRAM_API_ID=\nTELEGRAM_API_HASH=\n", encoding="utf-8")
    monkeypatch.setattr("check_env.ENV_PATH", env_path)

    problems = validate_env_file()

    assert any("TELEGRAM_API_ID is empty" in problem for problem in problems)
    assert any("TELEGRAM_API_HASH is empty" in problem for problem in problems)


def test_validate_env_file_ok(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TELEGRAM_API_ID=123456\nTELEGRAM_API_HASH=abc123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("check_env.ENV_PATH", env_path)

    assert validate_env_file() == []
