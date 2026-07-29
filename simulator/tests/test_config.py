"""Tests for simulator configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulator.config import SimulationSettings, load_simulation_settings
from simulator.enums import EnvironmentType, SimulationSpeed
from simulator.exceptions import ConfigurationError
from simulator.tests.conftest import make_settings


class TestSimulationSettings:
    def test_loads_defaults_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SIMULATION_ENABLED", raising=False)
        monkeypatch.delenv("SIMULATION_DEFAULT_ENVIRONMENT", raising=False)
        monkeypatch.delenv("SIMULATION_LIVE_DATABASE_NAME", raising=False)
        monkeypatch.delenv("SIMULATION_SIMULATION_DATABASE_NAME", raising=False)
        load_simulation_settings.cache_clear()
        settings = load_simulation_settings()
        assert settings.enabled is False
        assert settings.default_environment == EnvironmentType.LIVE
        assert settings.default_speed == SimulationSpeed.REALTIME
        assert settings.strict_isolation_enabled is True
        assert settings.live_database_name != settings.simulation_database_name

    def test_enabled_flag_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMULATION_ENABLED", "true")
        load_simulation_settings.cache_clear()
        settings = load_simulation_settings()
        assert settings.enabled is True

    def test_invalid_environment_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMULATION_DEFAULT_ENVIRONMENT", "not-a-real-env")
        load_simulation_settings.cache_clear()
        with pytest.raises(ConfigurationError):
            load_simulation_settings()

    def test_same_database_names_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMULATION_LIVE_DATABASE_NAME", "same_db")
        monkeypatch.setenv("SIMULATION_SIMULATION_DATABASE_NAME", "same_db")
        load_simulation_settings.cache_clear()
        with pytest.raises(ConfigurationError):
            load_simulation_settings()

    def test_database_name_for_environment(self) -> None:
        settings = make_settings()
        assert settings.database_name_for(EnvironmentType.LIVE) == "telegram_scraper"
        assert settings.database_name_for(EnvironmentType.SIMULATION) == "test_simulation_db"

    def test_export_path_for_environment(self) -> None:
        settings = make_settings()
        assert settings.export_path_for(EnvironmentType.LIVE) == Path("/tmp/live-export")
        assert settings.export_path_for(EnvironmentType.SIMULATION) == Path("/tmp/sim-export")

    def test_to_configuration_dict(self) -> None:
        settings = make_settings(
            enabled=True,
            default_environment=EnvironmentType.SIMULATION,
            default_speed=SimulationSpeed.FAST,
            random_seed=7,
        )
        data = settings.to_configuration_dict()
        assert data["enabled"] is True
        assert data["default_environment"] == "simulation"
        assert data["default_speed"] == "fast"
        assert data["strict_isolation_enabled"] is True
        assert data["live_database_name"] == "telegram_scraper"

    def test_backwards_compatible_aliases(self) -> None:
        settings = make_settings(simulation_database_name="sim_db")
        assert settings.database_name == "sim_db"
        assert settings.export_path == settings.simulation_export_path
