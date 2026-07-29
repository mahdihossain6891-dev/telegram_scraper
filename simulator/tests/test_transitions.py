"""Tests for transition validation."""

from __future__ import annotations

import pytest

from simulator.environment.transitions import (
    assert_simulation_state_transition,
    can_switch_environment,
    can_transition_simulation_state,
)
from simulator.enums import EnvironmentType, SimulationState
from simulator.exceptions import InvalidStateTransition


class TestTransitions:
    def test_valid_simulation_transitions(self) -> None:
        assert can_transition_simulation_state(
            SimulationState.READY, SimulationState.RUNNING
        )
        assert can_transition_simulation_state(
            SimulationState.RUNNING, SimulationState.PAUSED
        )

    def test_invalid_simulation_transition_raises(self) -> None:
        with pytest.raises(InvalidStateTransition):
            assert_simulation_state_transition(
                SimulationState.INITIALIZED, SimulationState.RUNNING
            )

    def test_environment_switch_requires_simulation_enabled(self) -> None:
        allowed = can_switch_environment(
            current=EnvironmentType.LIVE,
            target=EnvironmentType.SIMULATION,
            simulation_enabled=False,
            simulation_state=SimulationState.READY,
            strict_isolation=True,
            allow_future_environments=False,
        )
        assert allowed is False

    def test_cannot_leave_simulation_while_running(self) -> None:
        allowed = can_switch_environment(
            current=EnvironmentType.SIMULATION,
            target=EnvironmentType.LIVE,
            simulation_enabled=True,
            simulation_state=SimulationState.RUNNING,
            strict_isolation=True,
            allow_future_environments=False,
        )
        assert allowed is False

    def test_can_return_to_live_when_stopped(self) -> None:
        allowed = can_switch_environment(
            current=EnvironmentType.SIMULATION,
            target=EnvironmentType.LIVE,
            simulation_enabled=True,
            simulation_state=SimulationState.STOPPED,
            strict_isolation=True,
            allow_future_environments=False,
        )
        assert allowed is True
