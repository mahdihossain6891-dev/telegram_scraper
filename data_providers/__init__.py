"""Console data providers — live production data only."""

from __future__ import annotations

from data_providers.base import DataProvider
from data_providers.router import get_data_provider

__all__ = [
    "DataProvider",
    "ProductionDataProvider",
    "get_data_provider",
]


def __getattr__(name: str):
    if name == "ProductionDataProvider":
        from data_providers.production import ProductionDataProvider

        return ProductionDataProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
