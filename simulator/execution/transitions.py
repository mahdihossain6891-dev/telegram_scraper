"""Session lifecycle transition rules."""

from __future__ import annotations

from simulator.exceptions import InvalidSessionTransition
from simulator.execution.labels import SessionStatus

SESSION_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.INITIALIZING: frozenset({SessionStatus.READY, SessionStatus.FAILED, SessionStatus.CANCELLED}),
    SessionStatus.READY: frozenset({SessionStatus.RUNNING, SessionStatus.CANCELLED, SessionStatus.FAILED}),
    SessionStatus.RUNNING: frozenset(
        {SessionStatus.PAUSED, SessionStatus.STOPPING, SessionStatus.FAILED, SessionStatus.COMPLETED}
    ),
    SessionStatus.PAUSED: frozenset({SessionStatus.RUNNING, SessionStatus.STOPPING, SessionStatus.CANCELLED, SessionStatus.FAILED}),
    SessionStatus.STOPPING: frozenset({SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED}),
    SessionStatus.COMPLETED: frozenset(),
    SessionStatus.FAILED: frozenset(),
    SessionStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED}
)


def can_transition_session(current: SessionStatus, target: SessionStatus) -> bool:
    if current == target:
        return True
    return target in SESSION_TRANSITIONS.get(current, frozenset())


def assert_session_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition_session(current, target):
        raise InvalidSessionTransition(
            f"Cannot transition session from {current.value} to {target.value}."
        )
