"""EnvironmentManager — single source of truth for LIVE vs SIMULATION."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from simulator.config import SimulationSettings, load_simulation_settings
from simulator.contexts.database import DatabaseContext
from simulator.environment.context import (
    base_environment_metadata,
    build_environment_information,
    message_source_kind_for,
)
from simulator.environment.transitions import (
    can_switch_environment,
    environment_switch_reason,
)
from simulator.enums import EnvironmentType, SimulationState
from simulator.exceptions import EnvironmentError, InvalidEnvironmentTransition
from simulator.logger import get_prefixed_logger
from simulator.models.message_event import EnvironmentInformation
from simulator.sources.base import MessageSource
from simulator.sources.simulation import SimulationSource
from simulator.sources.telethon import TelethonSource


class EnvironmentManager:
    """Controls operating environment and coordinates isolated resources.

    Every future simulator module must obtain its environment through this
    manager — never by reading flags directly.
    """

    def __init__(
        self,
        *,
        settings: SimulationSettings | None = None,
        logger: logging.LoggerAdapter | None = None,
        initial: EnvironmentType | None = None,
        simulation_state_provider: Callable[[], SimulationState] | None = None,
        simulation_enabled_provider: Callable[[], bool] | None = None,
        telethon_source: TelethonSource | None = None,
        simulation_source: SimulationSource | None = None,
    ) -> None:
        self._settings = settings or load_simulation_settings()
        self._log = logger or get_prefixed_logger("environment", name="manager")
        self._simulation_state_provider = simulation_state_provider or (
            lambda: SimulationState.INITIALIZED
        )
        self._simulation_enabled_provider = simulation_enabled_provider or (
            lambda: self._settings.enabled
        )
        self._telethon_source = telethon_source or TelethonSource()
        self._simulation_source = simulation_source or SimulationSource()
        self._current = initial or self._settings.default_environment
        self.validate_environment(self._current)
        self._activate_sources_for(self._current)

    @property
    def current(self) -> EnvironmentType:
        """Active environment type."""
        return self._current

    def get_current_environment(self) -> EnvironmentType:
        """Return the active environment."""
        return self._current

    def get_simulation_state(self) -> SimulationState:
        """Return the current simulator lifecycle state (for transition guards)."""
        return self._simulation_state_provider()

    def switch_environment(self, environment: EnvironmentType) -> EnvironmentInformation:
        """Switch to another environment after validation."""
        self.validate_environment(environment)
        if not self.can_switch_to(environment):
            reason = environment_switch_reason(
                current=self._current,
                target=environment,
                simulation_enabled=self._simulation_enabled_provider(),
                simulation_state=self.get_simulation_state(),
                strict_isolation=self._settings.strict_isolation_enabled,
                allow_future_environments=self._settings.allow_future_environments,
            )
            raise InvalidEnvironmentTransition(reason or "Environment switch not allowed.")

        if environment == self._current:
            self._log.debug("Already on environment %s", environment.value)
        else:
            self._log.info(
                "Switching environment %s -> %s",
                self._current.value,
                environment.value,
            )
            self._deactivate_sources_for(self._current)
            self._current = environment
            self._activate_sources_for(self._current)
        return self.get_environment_information(environment)

    def can_switch_to(self, environment: EnvironmentType) -> bool:
        """Return whether switching to ``environment`` is currently allowed."""
        try:
            self.validate_environment(environment)
        except EnvironmentError:
            return False
        return can_switch_environment(
            current=self._current,
            target=environment,
            simulation_enabled=self._simulation_enabled_provider(),
            simulation_state=self.get_simulation_state(),
            strict_isolation=self._settings.strict_isolation_enabled,
            allow_future_environments=self._settings.allow_future_environments,
        )

    def validate_environment(self, environment: EnvironmentType) -> None:
        """Raise ``EnvironmentError`` if the environment cannot be selected."""
        active = EnvironmentType.active_types()
        if environment not in active:
            if self._settings.allow_future_environments:
                return
            raise EnvironmentError(
                f"Environment {environment.value!r} is not available in this phase."
            )

    def get_database_context(
        self, environment: EnvironmentType | None = None
    ) -> DatabaseContext:
        """Return the isolated database namespace for an environment."""
        env = environment or self._current
        return DatabaseContext(
            environment=env,
            database_name=self._settings.database_name_for(env),
            strict_isolation=self._settings.strict_isolation_enabled,
        )

    def get_message_source(
        self, environment: EnvironmentType | None = None
    ) -> MessageSource:
        """Return the active message source for an environment."""
        env = environment or self._current
        if env == EnvironmentType.LIVE:
            return self._telethon_source
        if env == EnvironmentType.SIMULATION:
            return self._simulation_source
        raise EnvironmentError(
            f"No message source registered for environment {env.value!r}."
        )

    def get_active_database_context(self) -> DatabaseContext:
        """Return database context for the currently active environment."""
        return self.get_database_context(self._current)

    def get_active_message_source(self) -> MessageSource:
        """Return message source for the currently active environment."""
        return self.get_message_source(self._current)

    def get_environment_information(
        self, environment: EnvironmentType | None = None
    ) -> EnvironmentInformation:
        """Return metadata for an environment (defaults to current)."""
        env = environment or self._current
        active_types = EnvironmentType.active_types()
        selectable = env in active_types and self.can_switch_to(env)
        metadata = base_environment_metadata(
            environment=env,
            strict_isolation=self._settings.strict_isolation_enabled,
            live_database_name=self._settings.live_database_name,
            simulation_database_name=self._settings.simulation_database_name,
            message_source_kind=message_source_kind_for(env),
        )
        metadata["database_name"] = self._settings.database_name_for(env)
        metadata["export_path"] = str(self._settings.export_path_for(env))
        metadata["database_context"] = self.get_database_context(env).to_dict()
        return build_environment_information(
            environment=env,
            active=env == self._current,
            selectable=selectable,
            metadata=metadata,
        )

    def list_environments(self) -> list[EnvironmentInformation]:
        """Describe all known environments (including future reserved types)."""
        return [self.get_environment_information(e) for e in EnvironmentType]

    def get_metadata(self) -> dict[str, Any]:
        """Return a snapshot of the active environment and isolation settings."""
        return {
            "active_environment": self._current.value,
            "simulation_state": self.get_simulation_state().value,
            "strict_isolation": self._settings.strict_isolation_enabled,
            "message_source": self.get_active_message_source().describe(),
            "database_context": self.get_active_database_context().to_dict(),
        }

    def _activate_sources_for(self, environment: EnvironmentType) -> None:
        if environment == EnvironmentType.LIVE:
            self._simulation_source.deactivate()
            self._telethon_source.activate()
        elif environment == EnvironmentType.SIMULATION:
            self._telethon_source.deactivate()
            self._simulation_source.activate()
        self._log.debug(
            "Message sources aligned for environment %s", environment.value
        )

    def _deactivate_sources_for(self, environment: EnvironmentType) -> None:
        if environment == EnvironmentType.LIVE:
            self._telethon_source.deactivate()
        elif environment == EnvironmentType.SIMULATION:
            self._simulation_source.deactivate()
