"""Tests for EnvironmentService."""

from __future__ import annotations

from simulator.enums import EnvironmentType
from simulator.environment import EnvironmentManager, EnvironmentService
from simulator.sources.simulation import SimulationSource
from simulator.sources.telethon import TelethonSource
from simulator.tests.conftest import make_settings


class TestEnvironmentService:
    def test_resolves_live_contexts(self) -> None:
        settings = make_settings()
        env_mgr = EnvironmentManager(settings=settings)
        service = EnvironmentService(settings=settings, environment_manager=env_mgr)

        assert service.resolve_active_environment() == EnvironmentType.LIVE
        assert isinstance(service.resolve_message_source(), TelethonSource)
        storage = service.resolve_storage()
        assert storage.database_name == settings.live_database_name
        ai = service.resolve_ai_context()
        assert ai.vector_namespace == "live_vectors"
        graph = service.resolve_graph_context()
        assert graph.environment == EnvironmentType.LIVE

    def test_resolves_simulation_contexts(self) -> None:
        settings = make_settings(enabled=True)
        env_mgr = EnvironmentManager(
            settings=settings,
            simulation_enabled_provider=lambda: True,
        )
        env_mgr.switch_environment(EnvironmentType.SIMULATION)
        service = EnvironmentService(settings=settings, environment_manager=env_mgr)

        assert service.resolve_active_environment() == EnvironmentType.SIMULATION
        assert isinstance(service.resolve_message_source(), SimulationSource)
        storage = service.resolve_storage()
        assert storage.database_name == settings.simulation_database_name
        ai = service.resolve_ai_context()
        assert ai.vector_namespace == "simulation_vectors"
        export = service.resolve_export_location()
        assert export == settings.simulation_export_path
