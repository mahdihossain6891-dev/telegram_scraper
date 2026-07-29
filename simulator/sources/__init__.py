"""Message source adapters."""

from __future__ import annotations

from simulator.sources.base import MessageSource
from simulator.sources.simulation import SimulationSource
from simulator.sources.telethon import TelethonSource

__all__ = ["MessageSource", "SimulationSource", "TelethonSource"]
