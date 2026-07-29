"""Return the live production data provider."""

from __future__ import annotations

from data_providers.base import DataProvider


def get_data_provider() -> DataProvider:
    """Return the active provider — always live production data."""
    from data_providers.production import ProductionDataProvider

    return ProductionDataProvider()
