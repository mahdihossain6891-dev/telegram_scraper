"""Thread-safe global console mode state (live vs simulation)."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Literal

from data_providers.persistence import (
    clear_persisted_mode,
    load_persisted_mode,
    save_persisted_mode,
)

ConsoleMode = Literal["live", "simulation"]


@dataclass(slots=True)
class ConsoleModeState:
    """Current console data mode — never mixes production and simulation."""

    mode: ConsoleMode = "live"
    simulation_active: bool = False
    scenario: str | None = None
    session_id: str | None = None
    session_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "simulation_active": self.simulation_active,
            "scenario": self.scenario,
            "session_id": self.session_id,
            "session_name": self.session_name,
        }


_lock = threading.Lock()
_state = ConsoleModeState()
_restored = False


def _restore_from_disk() -> None:
    global _restored
    if _restored:
        return
    _restored = True
    payload = load_persisted_mode()
    if not payload:
        return
    mode = str(payload.get("mode") or "live").lower()
    if mode != "simulation" or not payload.get("simulation_active"):
        return
    _state.mode = "simulation"
    _state.simulation_active = True
    _state.scenario = payload.get("scenario")
    _state.session_id = payload.get("session_id") or "sim-console"
    _state.session_name = payload.get("session_name")


def get_mode_state() -> ConsoleModeState:
    with _lock:
        _restore_from_disk()
        return ConsoleModeState(
            mode=_state.mode,
            simulation_active=_state.simulation_active,
            scenario=_state.scenario,
            session_id=_state.session_id,
            session_name=_state.session_name,
        )


def update_mode_state(**kwargs: Any) -> ConsoleModeState:
    with _lock:
        _restore_from_disk()
        for key, value in kwargs.items():
            if hasattr(_state, key):
                setattr(_state, key, value)
        snapshot = ConsoleModeState(
            mode=_state.mode,
            simulation_active=_state.simulation_active,
            scenario=_state.scenario,
            session_id=_state.session_id,
            session_name=_state.session_name,
        )
    if snapshot.mode == "simulation" and snapshot.simulation_active:
        save_persisted_mode(snapshot.to_dict())
    else:
        clear_persisted_mode()
    return snapshot


def reset_to_live() -> ConsoleModeState:
    with _lock:
        _restore_from_disk()
        _state.mode = "live"
        _state.simulation_active = False
        _state.scenario = None
        _state.session_id = None
        _state.session_name = None
    clear_persisted_mode()
    return get_mode_state()
