"""Tests for configuration module."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _reload_config():
    """Reload config module to pick up changed environment variables."""
    if "config" in sys.modules:
        return importlib.reload(sys.modules["config"])
    import config

    return config


class TestLoadSettings:
    """Tests for load_settings()."""

    def test_loads_valid_settings(self, env_vars: dict[str, str]) -> None:
        config = _reload_config()
        settings = config.load_settings()

        assert settings.telegram_api_id == 12345678
        assert settings.telegram_api_hash == "test_api_hash_value"
        assert settings.telegram_phone == "+10000000000"
        assert settings.telegram_session_name == "test_session"
        assert settings.log_level == "DEBUG"

    def test_session_path_resolves_under_data_dir(self, env_vars: dict[str, str]) -> None:
        config = _reload_config()
        settings = config.load_settings()

        assert settings.session_path == settings.data_dir / "test_session"

    def test_database_path_resolves_relative_url(self, env_vars: dict[str, str]) -> None:
        config = _reload_config()
        settings = config.load_settings()

        expected = settings.project_root / "data" / "test.db"
        assert settings.database_path == expected

    def test_missing_api_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        # Prevent .env from re-populating deleted vars during module reload.
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
        config = _reload_config()

        with pytest.raises(ValueError, match="TELEGRAM_API_ID"):
            config.load_settings()

    def test_invalid_api_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "not-a-number")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        config = _reload_config()

        with pytest.raises(ValueError, match="must be an integer"):
            config.load_settings()

    def test_invalid_log_level_raises(self, env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
        config = _reload_config()

        with pytest.raises(ValueError, match="LOG_LEVEL"):
            config.load_settings()

    def test_optional_phone_can_be_empty(self, env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_PHONE", "")
        config = _reload_config()
        settings = config.load_settings()

        assert settings.telegram_phone is None


class TestEnsureDirectories:
    """Tests for ensure_directories()."""

    def test_creates_required_directories(self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_project)
        sys.path.insert(0, str(tmp_project))
        try:
            config = _reload_config()
            settings = config.ensure_directories()

            assert settings.data_dir.is_dir()
            assert settings.exports_dir.is_dir()
            assert settings.log_file.parent.is_dir()
        finally:
            sys.path.remove(str(tmp_project))
