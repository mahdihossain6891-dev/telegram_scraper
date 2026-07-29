"""Console data providers — live production vs isolated simulation."""

from __future__ import annotations

from data_providers.base import DataProvider
from data_providers.state import ConsoleModeState

__all__ = [
    "ConsoleModeState",
    "DataProvider",
    "ProductionDataProvider",
    "SimulationDataProvider",
    "end_simulation_mode",
    "get_data_provider",
    "get_mode_state",
    "set_simulation_mode",
    "start_simulation_mode",
]


def __getattr__(name: str):
    if name == "ProductionDataProvider":
        from data_providers.production import ProductionDataProvider

        return ProductionDataProvider
    if name == "SimulationDataProvider":
        from data_providers.simulation import SimulationDataProvider

        return SimulationDataProvider
    if name in {
        "end_simulation_mode",
        "get_data_provider",
        "get_mode_state",
        "set_simulation_mode",
        "start_simulation_mode",
    }:
        from data_providers import router as router_mod

        return getattr(router_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
