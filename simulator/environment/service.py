"""EnvironmentService — gateway for resolving isolated runtime resources."""

from __future__ import annotations

from pathlib import Path

from simulator.config import SimulationSettings, load_simulation_settings
from simulator.contexts.ai import AIContext
from simulator.contexts.database import DatabaseContext
from simulator.contexts.graph import GraphContext
from simulator.environment.manager import EnvironmentManager
from simulator.enums import EnvironmentType
from simulator.sources.base import MessageSource


class EnvironmentService:
    """Resolves environment, storage, sources, and auxiliary contexts.

    Future simulator modules should depend on this service rather than
    constructing contexts directly.
    """

    def __init__(
        self,
        *,
        settings: SimulationSettings | None = None,
        environment_manager: EnvironmentManager | None = None,
    ) -> None:
        self._settings = settings or load_simulation_settings()
        self._environment = environment_manager or EnvironmentManager(
            settings=self._settings
        )

    @property
    def environment_manager(self) -> EnvironmentManager:
        return self._environment

    def resolve_active_environment(self) -> EnvironmentType:
        return self._environment.get_current_environment()

    def resolve_message_source(self) -> MessageSource:
        return self._environment.get_active_message_source()

    def resolve_storage(self) -> DatabaseContext:
        return self._environment.get_active_database_context()

    def resolve_database_context(
        self, environment: EnvironmentType | None = None
    ) -> DatabaseContext:
        return self._environment.get_database_context(environment)

    def resolve_ai_context(
        self, environment: EnvironmentType | None = None
    ) -> AIContext:
        env = environment or self._environment.get_current_environment()
        prefix = "live" if env == EnvironmentType.LIVE else env.value
        db = self._environment.get_database_context(env)
        return AIContext(
            environment=env,
            vector_namespace=f"{prefix}_vectors",
            session_collection=db.collection_name("ai_sessions"),
            report_collection=db.collection_name("ai_reports"),
        )

    def resolve_graph_context(
        self, environment: EnvironmentType | None = None
    ) -> GraphContext:
        env = environment or self._environment.get_current_environment()
        export = self.resolve_export_location(env)
        return GraphContext(
            environment=env,
            graph_namespace=f"{env.value}_relationship_graph",
            export_path=str(export),
        )

    def resolve_export_location(
        self, environment: EnvironmentType | None = None
    ) -> Path:
        env = environment or self._environment.get_current_environment()
        return self._settings.export_path_for(env)
