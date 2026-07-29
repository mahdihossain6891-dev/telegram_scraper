"""Tests for EnvironmentManager."""

from __future__ import annotations

import pytest

from simulator.enums import EnvironmentType, SimulationState
from simulator.environment import EnvironmentManager
from simulator.exceptions import EnvironmentError, InvalidEnvironmentTransition
from simulator.sources.simulation import SimulationSource
from simulator.sources.telethon import TelethonSource
from simulator.tests.conftest import make_settings


class TestEnvironmentManager:
    def test_initializes_with_default_environment(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings())
        assert env_mgr.get_current_environment() == EnvironmentType.LIVE
        assert env_mgr.get_active_message_source().is_active() is True

    def test_switch_environment_when_enabled(self) -> None:
        env_mgr = EnvironmentManager(
            settings=make_settings(enabled=True),
            simulation_enabled_provider=lambda: True,
        )
        info = env_mgr.switch_environment(EnvironmentType.SIMULATION)
        assert env_mgr.get_current_environment() == EnvironmentType.SIMULATION
        assert info.active is True
        assert isinstance(env_mgr.get_active_message_source(), SimulationSource)

    def test_switch_back_to_live(self) -> None:
        env_mgr = EnvironmentManager(
            settings=make_settings(enabled=True),
            simulation_enabled_provider=lambda: True,
        )
        env_mgr.switch_environment(EnvironmentType.SIMULATION)
        env_mgr.switch_environment(EnvironmentType.LIVE)
        assert isinstance(env_mgr.get_active_message_source(), TelethonSource)

    def test_simulation_switch_blocked_when_not_enabled(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings(enabled=False))
        with pytest.raises(InvalidEnvironmentTransition):
            env_mgr.switch_environment(EnvironmentType.SIMULATION)

    def test_reserved_environment_not_selectable(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings())
        with pytest.raises(EnvironmentError):
            env_mgr.switch_environment(EnvironmentType.PLAYBACK)

    def test_list_environments_includes_future_types(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings())
        all_envs = env_mgr.list_environments()
        keys = {e.environment for e in all_envs}
        assert EnvironmentType.PLAYBACK in keys
        playback = next(e for e in all_envs if e.environment == EnvironmentType.PLAYBACK)
        assert playback.selectable is False

    def test_database_context_isolation(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings())
        live_ctx = env_mgr.get_database_context(EnvironmentType.LIVE)
        sim_ctx = env_mgr.get_database_context(EnvironmentType.SIMULATION)
        assert live_ctx.database_name != sim_ctx.database_name
        assert live_ctx.environment == EnvironmentType.LIVE
        assert sim_ctx.environment == EnvironmentType.SIMULATION

    def test_blocked_live_switch_while_simulator_running(self) -> None:
        env_mgr = EnvironmentManager(
            settings=make_settings(enabled=True),
            simulation_state_provider=lambda: SimulationState.RUNNING,
            simulation_enabled_provider=lambda: True,
        )
        env_mgr.switch_environment(EnvironmentType.SIMULATION)
        with pytest.raises(InvalidEnvironmentTransition):
            env_mgr.switch_environment(EnvironmentType.LIVE)

    def test_environment_information_serializes(self) -> None:
        env_mgr = EnvironmentManager(settings=make_settings())
        data = env_mgr.get_environment_information().to_dict()
        assert data["environment"] == EnvironmentType.LIVE.value
        assert "description" in data
        assert "metadata" in data
