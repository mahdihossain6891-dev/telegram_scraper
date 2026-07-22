"""Tests for console data provider routing."""

from __future__ import annotations

from data_providers.router import end_simulation_mode, get_data_provider, get_mode_state
from data_providers.state import reset_to_live
from data_providers.simulation import SimulationDataProvider


def test_default_mode_is_live() -> None:
    reset_to_live()
    state = get_mode_state()
    assert state.mode == "live"
    assert state.simulation_active is False
    assert isinstance(get_data_provider(), SimulationDataProvider) is False
    assert get_data_provider().mode == "live"


def test_end_simulation_returns_to_live() -> None:
    reset_to_live()
    end = end_simulation_mode()
    assert end.mode == "live"
    assert end.simulation_active is False


def test_simulation_provider_mode_label() -> None:
    provider = SimulationDataProvider(session_id="test-session", scenario="narcotics")
    assert provider.mode == "simulation"
    assert provider.source_label == "simulation"
    assert provider.allows_live_operations() is False
