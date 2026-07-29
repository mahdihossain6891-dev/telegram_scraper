"""Tests for simulator logging."""

from __future__ import annotations

import logging

import pytest

from simulator.constants import LOG_MESSAGE_PREFIX
from simulator.logger import get_simulator_logger


class TestSimulatorLogger:
    def test_prefixes_messages(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = get_simulator_logger("tests")
        with caplog.at_level(logging.DEBUG, logger="simulator.tests"):
            logger.info("lifecycle event")
        assert any(LOG_MESSAGE_PREFIX in r.message for r in caplog.records)
