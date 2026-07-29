"""Shared Threat Simulation facade instance for API + data providers."""

from __future__ import annotations

from simulator.api.facade import SimulationConsoleFacade

_facade: SimulationConsoleFacade | None = None


def get_simulator_facade() -> SimulationConsoleFacade:
    global _facade
    if _facade is None:
        _facade = SimulationConsoleFacade()
    return _facade
