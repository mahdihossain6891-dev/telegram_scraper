"""Simulation message source — placeholder (no generation in Phase 2)."""

from __future__ import annotations

from simulator.enums import EnvironmentType, MessageSourceKind
from simulator.logger import get_prefixed_logger
from simulator.sources.base import MessageSource

_log = get_prefixed_logger("source", name="simulation")


class SimulationSource(MessageSource):
    """Synthetic Telegram traffic for SIMULATION environment.

    Phase 2: dormant placeholder. Message generation arrives in a later phase.
    """

    def __init__(self) -> None:
        self._active = False
        _log.debug("SimulationSource placeholder initialized (inactive)")

    @property
    def environment(self) -> EnvironmentType:
        return EnvironmentType.SIMULATION

    @property
    def source_kind(self) -> MessageSourceKind:
        return MessageSourceKind.SIMULATION

    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        self._active = True
        _log.info("SimulationSource marked active (placeholder — no generation)")

    def deactivate(self) -> None:
        self._active = False
        _log.info("SimulationSource deactivated")
