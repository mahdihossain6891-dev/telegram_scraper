"""Tests for utilities module."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest


def _reload_utils():
    """Reload utils module after config changes."""
    if "utils" in sys.modules:
        return importlib.reload(sys.modules["utils"])
    import utils

    return utils


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_configures_logger_with_file_and_console(
        self,
        tmp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_project)
        sys.path.insert(0, str(tmp_project))
        try:
            import config as config_module

            importlib.reload(config_module)
            utils = _reload_utils()

            settings = config_module.load_settings()
            logger = utils.setup_logging(settings)

            assert logger.name == "telegram_scraper"
            assert logger.level == logging.DEBUG
            assert len(logger.handlers) == 2

            logger.info("test log message")
            assert settings.log_file.exists()
            content = settings.log_file.read_text(encoding="utf-8")
            assert "test log message" in content
        finally:
            sys.path.remove(str(tmp_project))

    def test_idempotent_setup(self, env_vars: dict[str, str]) -> None:
        utils = _reload_utils()
        import config as config_module

        importlib.reload(config_module)
        settings = config_module.load_settings()

        logger_first = utils.setup_logging(settings)
        handler_count_first = len(logger_first.handlers)

        logger_second = utils.setup_logging(settings)
        assert len(logger_second.handlers) == handler_count_first


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_namespaced_logger(self, env_vars: dict[str, str]) -> None:
        utils = _reload_utils()
        child = utils.get_logger("scraper")
        assert child.name == "telegram_scraper.scraper"
