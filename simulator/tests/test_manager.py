"""Tests for SimulationManager."""

from __future__ import annotations

import pytest

from simulator.enums import EnvironmentType, SimulationSpeed, SimulationState
from simulator.exceptions import (
    InvalidEnvironmentTransition,
    SimulatorAlreadyRunning,
    SimulatorNotEnabled,
    SimulatorNotRunning,
)
from simulator.manager import SimulationManager
from simulator.tests.conftest import make_settings


class TestSimulationManager:
    def test_initializes_disabled_by_default(self) -> None:
        mgr = SimulationManager(settings=make_settings(enabled=False))
        status = mgr.get_status()
        assert status.enabled is False
        assert status.state == SimulationState.INITIALIZED
        assert status.active_environment == EnvironmentType.LIVE

    def test_enable_and_lifecycle(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        assert mgr.get_status().state == SimulationState.READY

        mgr.start()
        status = mgr.get_status()
        assert status.state == SimulationState.RUNNING
        assert status.active_environment == EnvironmentType.SIMULATION

        mgr.pause()
        assert mgr.get_status().state == SimulationState.PAUSED

        mgr.resume()
        assert mgr.get_status().state == SimulationState.RUNNING

        mgr.stop()
        status = mgr.get_status()
        assert status.state == SimulationState.STOPPED
        assert status.active_environment == EnvironmentType.LIVE

        mgr.reset()
        assert mgr.get_status().state == SimulationState.READY

    def test_start_requires_enabled(self) -> None:
        mgr = SimulationManager(settings=make_settings(enabled=False))
        with pytest.raises(SimulatorNotEnabled):
            mgr.start()

    def test_environment_switch_blocked_without_simulation_flag(self) -> None:
        mgr = SimulationManager(settings=make_settings(enabled=False))
        with pytest.raises(InvalidEnvironmentTransition):
            mgr.environment_manager.switch_environment(EnvironmentType.SIMULATION)

    def test_double_start_raises(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        mgr.start()
        with pytest.raises(SimulatorAlreadyRunning):
            mgr.start()

    def test_pause_without_running_raises(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        with pytest.raises(SimulatorNotRunning):
            mgr.pause()

    def test_cannot_switch_to_live_while_running(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        mgr.start()
        with pytest.raises(InvalidEnvironmentTransition):
            mgr.environment_manager.switch_environment(EnvironmentType.LIVE)

    def test_get_configuration_reflects_settings(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        cfg = mgr.get_configuration()
        assert cfg.database_name == "test_simulation_db"
        assert cfg.live_database_name == "telegram_scraper"
        assert cfg.user_count == 10
        assert cfg.speed == SimulationSpeed.REALTIME
        assert cfg.strict_isolation is True

    def test_status_serializes(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        data = mgr.get_status().to_dict()
        assert data["state"] == SimulationState.READY.value
        assert data["active_environment"] == EnvironmentType.LIVE.value
        assert "configuration" in data

    def test_error_state_and_reset(self) -> None:
        mgr = SimulationManager(settings=make_settings())
        mgr.enable()
        mgr.mark_error("test failure")
        assert mgr.state == SimulationState.ERROR
        mgr.reset()
        assert mgr.state == SimulationState.READY
