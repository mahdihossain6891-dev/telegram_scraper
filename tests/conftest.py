"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import mongomock
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
        "DATABASE_URL": "mongodb://127.0.0.1:27017/telegram_scraper_test",
        "MONGODB_URI": "mongodb://127.0.0.1:27017/telegram_scraper_test",
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
    monkeypatch.setenv(
        "DATABASE_URL",
        f"mongodb://127.0.0.1:27017/test_{tmp_path.name}",
    )
    monkeypatch.setenv(
        "MONGODB_URI",
        f"mongodb://127.0.0.1:27017/test_{tmp_path.name}",
    )
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "logs" / "test.log"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EXPORTS_DIR", str(tmp_path / "exports"))
    return tmp_path


@pytest.fixture()
def db_settings(tmp_project: Path, monkeypatch: pytest.MonkeyPatch):
    """Configure an isolated MongoDB (mongomock) database for tests."""
    import database

    monkeypatch.chdir(tmp_project)
    sys.path.insert(0, str(PROJECT_ROOT))
    import config as config_module

    importlib.reload(config_module)
    db_module = importlib.reload(database)
    db_module.reset_engine_cache()

    mock_client = mongomock.MongoClient()
    monkeypatch.setattr(db_module, "get_client", lambda settings=None: mock_client)
    # Keep get_db using patched client
    def _get_db(settings=None):
        cfg = settings or config_module.load_settings()
        _, db_name = db_module._parse_mongo_settings(cfg.database_url)
        return mock_client[db_name]

    monkeypatch.setattr(db_module, "get_db", _get_db)

    settings = config_module.load_settings()
    db_module.init_db(settings)
    yield settings, db_module
    db_module.reset_engine_cache()
    if str(PROJECT_ROOT) in sys.path:
        sys.path.remove(str(PROJECT_ROOT))


@pytest.fixture()
def reset_console_mode():
    """Ensure console mode is live before and after each test."""
    from data_providers.state import reset_to_live

    reset_to_live()
    yield
    reset_to_live()


@pytest.fixture()
def sim_facade(monkeypatch):
    """Fresh in-memory simulator facade for isolated mode tests."""
    from simulator.api.facade import SimulationConsoleFacade
    import simulator.api.singleton as sim_singleton

    facade = SimulationConsoleFacade()
    monkeypatch.setattr(sim_singleton, "_facade", facade)
    monkeypatch.setattr("data_providers.router.get_simulator_facade", lambda: facade)
    monkeypatch.setattr("data_providers.simulation.get_simulator_facade", lambda: facade)
    return facade


@pytest.fixture()
def no_live_mongo(monkeypatch):
    """Prevent production provider from blocking on unreachable MongoDB."""
    monkeypatch.setattr("data_providers.production.database_available", lambda _settings: False)
