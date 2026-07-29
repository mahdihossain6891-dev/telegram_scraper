"""Tests for simulator metadata models."""

from __future__ import annotations

from datetime import datetime, timezone

from simulator.enums import EnvironmentType, SimulationSpeed, SimulationState
from simulator.models import (
    EnvironmentInformation,
    MessageEvent,
    SimulationConfiguration,
    SimulationStatus,
)


class TestModels:
    def test_message_event_serializes(self) -> None:
        event = MessageEvent(
            message_id=1,
            chat_id=100,
            sender_id=42,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            text="hello",
            environment=EnvironmentType.SIMULATION,
            metadata={"scenario": "test"},
        )
        data = event.to_dict()
        assert data["message_id"] == 1
        assert data["environment"] == "simulation"
        assert data["metadata"]["scenario"] == "test"

    def test_simulation_configuration_serializes(self) -> None:
        cfg = SimulationConfiguration(
            enabled=True,
            environment=EnvironmentType.SIMULATION,
            speed=SimulationSpeed.TURBO,
            user_count=100,
            group_count=20,
            database_name="sim_db",
            live_database_name="live_db",
            export_path="/tmp/export",
            random_seed=99,
            strict_isolation=True,
        )
        data = cfg.to_dict()
        assert data["environment"] == "simulation"
        assert data["live_database_name"] == "live_db"
        assert data["strict_isolation"] is True

    def test_simulation_status_serializes(self) -> None:
        cfg = SimulationConfiguration(
            enabled=False,
            environment=EnvironmentType.LIVE,
            speed=SimulationSpeed.REALTIME,
            user_count=0,
            group_count=0,
            database_name="db",
            export_path="exports",
        )
        status = SimulationStatus(
            state=SimulationState.READY,
            enabled=False,
            configuration=cfg,
            active_environment=EnvironmentType.LIVE,
            message="ok",
        )
        data = status.to_dict()
        assert data["state"] == "ready"
        assert data["active_environment"] == "live"
        assert data["configuration"]["database_name"] == "db"

    def test_environment_information_serializes(self) -> None:
        info = EnvironmentInformation(
            environment=EnvironmentType.LIVE,
            active=True,
            selectable=True,
            description="Live monitoring",
            metadata={"version": "0.2.0"},
        )
        data = info.to_dict()
        assert data["active"] is True
        assert data["metadata"]["version"] == "0.2.0"
