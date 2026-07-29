"""Tests for message source abstractions."""

from __future__ import annotations

from simulator.enums import EnvironmentType, MessageSourceKind
from simulator.sources.simulation import SimulationSource
from simulator.sources.telethon import TelethonSource


class TestMessageSources:
    def test_telethon_source_placeholder(self) -> None:
        source = TelethonSource()
        assert source.environment == EnvironmentType.LIVE
        assert source.source_kind == MessageSourceKind.TELETHON
        assert source.poll() == []
        source.activate()
        assert source.is_active() is True
        source.deactivate()
        assert source.is_active() is False

    def test_simulation_source_placeholder(self) -> None:
        source = SimulationSource()
        assert source.environment == EnvironmentType.SIMULATION
        assert source.source_kind == MessageSourceKind.SIMULATION
        assert source.poll() == []
        source.activate()
        assert source.is_active() is True

    def test_describe_metadata(self) -> None:
        source = TelethonSource()
        data = source.describe()
        assert data["source_kind"] == "telethon"
        assert data["environment"] == "live"
