"""Tests for simulator enums."""

from __future__ import annotations

from simulator.enums import EnvironmentType, MessageSourceKind, SimulationSpeed, SimulationState


class TestEnums:
    def test_environment_active_types(self) -> None:
        active = EnvironmentType.active_types()
        assert EnvironmentType.LIVE in active
        assert EnvironmentType.SIMULATION in active
        assert EnvironmentType.PLAYBACK not in active

    def test_simulation_state_values(self) -> None:
        assert SimulationState.INITIALIZED.value == "initialized"
        assert SimulationState.READY.value == "ready"
        assert SimulationState.RUNNING.value == "running"
        assert SimulationState.ERROR.value == "error"

    def test_simulation_speed_is_string_enum(self) -> None:
        assert SimulationSpeed.REALTIME.value == "realtime"
        assert isinstance(SimulationSpeed.FAST, SimulationSpeed)

    def test_message_source_kind_values(self) -> None:
        assert MessageSourceKind.TELETHON.value == "telethon"
        assert MessageSourceKind.SIMULATION.value == "simulation"
