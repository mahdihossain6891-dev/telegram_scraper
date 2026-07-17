"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide minimal valid environment variables for configuration tests."""
    values = {
        "TELEGRAM_API_ID": "12345678",
        "TELEGRAM_API_HASH": "test_api_hash_value",
        "TELEGRAM_PHONE": "+10000000000",
        "TELEGRAM_SESSION_NAME": "test_session",
        "DATABASE_URL": "sqlite:///data/test.db",
        "LOG_LEVEL": "DEBUG",
        "LOG_FILE": "logs/test.log",
        "DATA_DIR": "data",
        "EXPORTS_DIR": "exports",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture()
def tmp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create an isolated temporary project root with required directories."""
    for subdir in ("data", "exports", "logs"):
        (tmp_path / subdir).mkdir()
    monkeypatch.setenv("TELEGRAM_API_ID", "99999")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash_for_tmp_project")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'test.db'}")
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "logs" / "test.log"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EXPORTS_DIR", str(tmp_path / "exports"))
    return tmp_path


@pytest.fixture()
def db_settings(tmp_project: Path, monkeypatch: pytest.MonkeyPatch):
    """Configure an isolated SQLite database for tests."""
    import database

    monkeypatch.chdir(tmp_project)
    sys.path.insert(0, str(tmp_project))
    import config as config_module

    importlib.reload(config_module)
    db_module = importlib.reload(database)
    db_module.reset_engine_cache()

    settings = config_module.load_settings()
    db_module.init_db(settings)
    yield settings, db_module
    db_module.reset_engine_cache()
    sys.path.remove(str(tmp_project))
