"""Environment transition rules — validated before any switch."""

from __future__ import annotations

from simulator.enums import EnvironmentType, SimulationState

# Simulator lifecycle transitions (Phase 2).
SIMULATION_STATE_TRANSITIONS: dict[SimulationState, frozenset[SimulationState]] = {
    SimulationState.INITIALIZED: frozenset({SimulationState.READY, SimulationState.ERROR}),
    SimulationState.READY: frozenset(
        {
            SimulationState.RUNNING,
            SimulationState.STOPPED,
            SimulationState.ERROR,
            SimulationState.INITIALIZED,
        }
    ),
    SimulationState.RUNNING: frozenset(
        {SimulationState.PAUSED, SimulationState.STOPPED, SimulationState.ERROR}
    ),
    SimulationState.PAUSED: frozenset(
        {SimulationState.RUNNING, SimulationState.STOPPED, SimulationState.ERROR}
    ),
    SimulationState.STOPPED: frozenset(
        {SimulationState.READY, SimulationState.RUNNING, SimulationState.ERROR, SimulationState.INITIALIZED}
    ),
    SimulationState.ERROR: frozenset({SimulationState.READY, SimulationState.INITIALIZED}),
}

# Environment pairs that are always allowed when isolation rules pass.
_ALLOWED_ENVIRONMENT_PAIRS: frozenset[tuple[EnvironmentType, EnvironmentType]] = frozenset(
    {
        (EnvironmentType.LIVE, EnvironmentType.LIVE),
        (EnvironmentType.SIMULATION, EnvironmentType.SIMULATION),
        (EnvironmentType.LIVE, EnvironmentType.SIMULATION),
        (EnvironmentType.SIMULATION, EnvironmentType.LIVE),
    }
)

_ACTIVE_SIMULATOR_STATES = frozenset(
    {SimulationState.RUNNING, SimulationState.PAUSED}
)


def can_transition_simulation_state(
    current: SimulationState, target: SimulationState
) -> bool:
    """Return whether a simulator state change is legal."""
    if current == target:
        return True
    return target in SIMULATION_STATE_TRANSITIONS.get(current, frozenset())


def assert_simulation_state_transition(
    current: SimulationState, target: SimulationState
) -> None:
    """Raise ``InvalidStateTransition`` when the transition is illegal."""
    from simulator.exceptions import InvalidStateTransition

    if not can_transition_simulation_state(current, target):
        raise InvalidStateTransition(
            f"Cannot transition simulator from {current.value} to {target.value}."
        )


def can_switch_environment(
    *,
    current: EnvironmentType,
    target: EnvironmentType,
    simulation_enabled: bool,
    simulation_state: SimulationState,
    strict_isolation: bool,
    allow_future_environments: bool,
) -> bool:
    """Return whether an environment switch is permitted."""
    if current == target:
        return True

    if (current, target) not in _ALLOWED_ENVIRONMENT_PAIRS:
        return False

    active = EnvironmentType.active_types()
    if target not in active:
        return allow_future_environments

    if strict_isolation:
        if target == EnvironmentType.SIMULATION and not simulation_enabled:
            return False
        if (
            current == EnvironmentType.SIMULATION
            and target == EnvironmentType.LIVE
            and simulation_state in _ACTIVE_SIMULATOR_STATES
        ):
            return False

    return True


def environment_switch_reason(
    *,
    current: EnvironmentType,
    target: EnvironmentType,
    simulation_enabled: bool,
    simulation_state: SimulationState,
    strict_isolation: bool,
    allow_future_environments: bool,
) -> str | None:
    """Human-readable reason when ``can_switch_environment`` is False."""
    if current == target:
        return None

    if (current, target) not in _ALLOWED_ENVIRONMENT_PAIRS:
        return f"Transition {current.value} -> {target.value} is not supported."

    active = EnvironmentType.active_types()
    if target not in active and not allow_future_environments:
        return f"Environment {target.value!r} is reserved for a future phase."

    if strict_isolation and target == EnvironmentType.SIMULATION and not simulation_enabled:
        return "Simulation environment requires SIMULATION_ENABLED=true."

    if (
        strict_isolation
        and current == EnvironmentType.SIMULATION
        and target == EnvironmentType.LIVE
        and simulation_state in _ACTIVE_SIMULATOR_STATES
    ):
        return (
            "Cannot return to LIVE while simulator is running or paused. "
            "Stop the simulator first."
        )

    return "Environment switch blocked by isolation policy."
