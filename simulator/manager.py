"""SimulationManager — control plane for the Telegram Traffic Simulator.

Responsibilities:
    Lifecycle transitions (enable/start/pause/resume/stop/reset).
    Delegate environment switching to ``EnvironmentManager`` — never touch DBs.
"""

from __future__ import annotations

import logging
from typing import Any

from simulator.config import SimulationSettings, load_simulation_settings
from simulator.environment.manager import EnvironmentManager
from simulator.environment.transitions import assert_simulation_state_transition
from simulator.enums import EnvironmentType, SimulationState
from simulator.exceptions import (
    InvalidStateTransition,
    SimulatorAlreadyRunning,
    SimulatorNotEnabled,
    SimulatorNotRunning,
)
from simulator.logger import get_simulator_logger
from simulator.models import SimulationConfiguration, SimulationStatus


class SimulationManager:
    """Control-layer manager for simulator lifecycle (no database I/O)."""

    def __init__(
        self,
        *,
        settings: SimulationSettings | None = None,
        logger: logging.LoggerAdapter | None = None,
        provider: Any | None = None,
        environment_manager: EnvironmentManager | None = None,
        execution_engine: Any | None = None,
    ) -> None:
        self._settings = settings or load_simulation_settings()
        self._log = logger or get_simulator_logger("manager")
        self._provider = provider
        self._execution_engine = execution_engine
        self._enabled = self._settings.enabled
        self._state = (
            SimulationState.READY if self._enabled else SimulationState.INITIALIZED
        )
        self._environment = environment_manager or EnvironmentManager(
            settings=self._settings,
            simulation_state_provider=self.get_simulation_state,
            simulation_enabled_provider=lambda: self._enabled,
        )

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def environment_manager(self) -> EnvironmentManager:
        return self._environment

    @property
    def execution_engine(self) -> Any | None:
        """Optional Phase 7 execution engine (injected)."""
        return self._execution_engine

    def get_simulation_state(self) -> SimulationState:
        return self._state

    def enable(self) -> SimulationStatus:
        if self._enabled:
            self._log.debug("Simulator already enabled")
            return self.get_status()
        self._enabled = True
        self._transition_to(SimulationState.READY)
        self._log.info("Simulator enabled")
        return self.get_status()

    def disable(self) -> SimulationStatus:
        if not self._enabled:
            self._log.debug("Simulator already disabled")
            return self.get_status()
        if self._state in {SimulationState.RUNNING, SimulationState.PAUSED}:
            self.stop()
        self._enabled = False
        self._transition_to(SimulationState.INITIALIZED)
        self._log.info("Simulator disabled")
        return self.get_status()

    def start(self) -> SimulationStatus:
        self._require_enabled()
        if self._state == SimulationState.RUNNING:
            raise SimulatorAlreadyRunning("Simulator is already running.")
        self._transition_to(SimulationState.RUNNING)
        self._environment.switch_environment(EnvironmentType.SIMULATION)
        if self._execution_engine is not None:
            engine = self._execution_engine
            if engine.session is None:
                engine.initialize_session()
            if engine.session.status.value == "ready":
                engine.start()
        self._log.info("Simulator started — environment set to SIMULATION")
        return self.get_status()

    def pause(self) -> SimulationStatus:
        self._require_enabled()
        if self._state != SimulationState.RUNNING:
            raise SimulatorNotRunning("Cannot pause — simulator is not running.")
        self._transition_to(SimulationState.PAUSED)
        if self._execution_engine is not None and self._execution_engine.session is not None:
            self._execution_engine.pause()
        self._log.info("Simulator paused")
        return self.get_status()

    def resume(self) -> SimulationStatus:
        self._require_enabled()
        if self._state != SimulationState.PAUSED:
            raise SimulatorNotRunning("Cannot resume — simulator is not paused.")
        self._transition_to(SimulationState.RUNNING)
        self._log.info("Simulator resumed")
        return self.get_status()

    def stop(self) -> SimulationStatus:
        self._require_enabled()
        if self._state not in {SimulationState.RUNNING, SimulationState.PAUSED}:
            raise SimulatorNotRunning("Cannot stop — simulator is not active.")
        if self._execution_engine is not None:
            self._execution_engine.stop()
            self._execution_engine.shutdown()
        self._transition_to(SimulationState.STOPPED)
        self._environment.switch_environment(EnvironmentType.LIVE)
        self._log.info("Simulator stopped — environment restored to LIVE")
        return self.get_status()

    def reset(self) -> SimulationStatus:
        self._require_enabled()
        if self._state in {SimulationState.RUNNING, SimulationState.PAUSED}:
            self.stop()
        self._transition_to(SimulationState.READY)
        self._log.info("Simulator reset")
        return self.get_status()

    def mark_error(self, message: str = "") -> SimulationStatus:
        self._transition_to(SimulationState.ERROR)
        self._log.error("Simulator entered ERROR state%s", f": {message}" if message else "")
        return self.get_status()

    def get_status(self) -> SimulationStatus:
        return SimulationStatus(
            state=self._state,
            enabled=self._enabled,
            configuration=self.get_configuration(),
            active_environment=self._environment.get_current_environment(),
            message=self._status_message(),
        )

    def get_configuration(self) -> SimulationConfiguration:
        cfg = self._settings
        return SimulationConfiguration(
            enabled=self._enabled,
            environment=self._environment.get_current_environment(),
            speed=cfg.default_speed,
            user_count=cfg.default_users,
            group_count=cfg.default_groups,
            database_name=cfg.simulation_database_name,
            live_database_name=cfg.live_database_name,
            export_path=str(cfg.simulation_export_path),
            random_seed=cfg.random_seed,
            strict_isolation=cfg.strict_isolation_enabled,
        )

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise SimulatorNotEnabled(
                "Simulator is disabled. Call enable() before this operation."
            )

    def _transition_to(self, target: SimulationState) -> None:
        try:
            assert_simulation_state_transition(self._state, target)
        except InvalidStateTransition:
            if self._state != target:
                raise
        self._state = target

    def _status_message(self) -> str:
        if not self._enabled:
            return "Simulator is disabled (initialized)."
        env = self._environment.get_current_environment().value
        return f"Simulator is {self._state.value} (environment={env})."
