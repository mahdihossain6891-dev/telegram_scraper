"""SimulationExecutionEngine — central orchestrator for the simulator."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from simulator.checkpoint.store import CheckpointStore
from simulator.enums import EnvironmentType
from simulator.events.bus import EventBus
from simulator.events.types import EventType
from simulator.exceptions import ExecutionError, SessionError
from simulator.execution.config import ExecutionConfig
from simulator.execution.interfaces import ExecutionStep
from simulator.execution.labels import SessionStatus
from simulator.execution.loop import (
    CheckpointStep,
    ConversationStep,
    MetricsStep,
    PipelineStep,
    ScenarioStep,
    SchedulerStep,
)
from simulator.execution.session import SimulationSession
from simulator.execution.tick import SimulationTick
from simulator.execution.transitions import assert_session_transition, TERMINAL_STATUSES
from simulator.generation_config import GenerationConfig
from simulator.logger import get_prefixed_logger
from simulator.metrics.engine import MetricsEngine
from simulator.pipeline.controller import PipelineController
from simulator.pipeline.stages import default_pipeline_stages
from simulator.resources.manager import ResourceManager
from simulator.scenario.config import ScenarioConfig
from simulator.world_generator import GeneratedWorld, WorldGenerator

_log = get_prefixed_logger("execution", name="engine")


class SimulationExecutionEngine:
    """Coordinates simulator subsystems without containing business logic."""

    def __init__(
        self,
        *,
        execution_config: ExecutionConfig | None = None,
        generation_config: GenerationConfig | None = None,
        scenario_config: ScenarioConfig | None = None,
        pipeline_controller: PipelineController | None = None,
        event_bus: EventBus | None = None,
        metrics_engine: MetricsEngine | None = None,
        resource_manager: ResourceManager | None = None,
        checkpoint_store: CheckpointStore | None = None,
        world: GeneratedWorld | None = None,
        steps: list[ExecutionStep] | None = None,
        simulation_name: str = "default-simulation",
        scenario_manager: Any | None = None,
        conversation_manager: Any | None = None,
        scheduler: Any | None = None,
    ) -> None:
        self._execution_config = execution_config or ExecutionConfig(max_ticks=5)
        self._generation_config = generation_config or GenerationConfig(
            user_count=30,
            group_count=4,
            random_seed=42,
            maximum_concurrent_conversations=self._execution_config.max_active_conversations,
            simulation_speed_multiplier=self._execution_config.simulation_speed,
        )
        self._scenario_config = scenario_config or ScenarioConfig(
            random_seed=self._generation_config.random_seed,
        )
        self._event_bus = event_bus or EventBus()
        self._metrics = metrics_engine or MetricsEngine()
        self._resources = resource_manager or ResourceManager(queue_limit=self._execution_config.queue_size)
        self._checkpoints = checkpoint_store or CheckpointStore()
        self._world = world
        self._simulation_name = simulation_name

        from simulator.conversation.manager import ConversationManager
        from simulator.scheduler.manager import SchedulerManager
        from simulator.scenario.manager import ScenarioManager

        self._scenario_manager = scenario_manager or ScenarioManager(self._scenario_config)
        self._scheduler = scheduler or SchedulerManager(self._generation_config)
        self._conversation_manager = conversation_manager or ConversationManager(
            self._generation_config,
            scenario_manager=self._scenario_manager,
        )

        self._pipeline = pipeline_controller or PipelineController(
            default_pipeline_stages(),
            event_bus=self._event_bus,
            retry_count=self._execution_config.retry_count,
        )

        self._steps: list[ExecutionStep] = steps or [
            SchedulerStep(self._scheduler),
            ScenarioStep(self._scenario_manager),
            ConversationStep(self._conversation_manager),
            PipelineStep(self._pipeline),
            MetricsStep(),
            CheckpointStep(),
        ]

        self._session: SimulationSession | None = None
        self._runtime: dict[str, Any] = {}
        self._current_tick: SimulationTick | None = None
        self._paused = False
        self._stop_requested = False

    @property
    def session(self) -> SimulationSession | None:
        return self._session

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def metrics(self) -> MetricsEngine:
        return self._metrics

    @property
    def pipeline(self) -> PipelineController:
        return self._pipeline

    @property
    def steps(self) -> list[ExecutionStep]:
        return list(self._steps)

    def initialize_session(self) -> SimulationSession:
        """Create and prepare a new simulation session."""
        if self._session is not None and not self._session.is_terminal:
            raise SessionError("An active session already exists.")

        session = SimulationSession(
            session_id=uuid4(),
            simulation_name=self._simulation_name,
            creation_time=datetime.utcnow(),
            environment=EnvironmentType.SIMULATION,
            random_seed=self._generation_config.random_seed,
            scenario_configuration=self._scenario_config.to_dict(),
            user_count=self._generation_config.user_count,
            group_count=self._generation_config.group_count,
            scenario_distribution=dict(self._scenario_config.scenario_weights),
            simulation_speed=self._execution_config.simulation_speed,
        )
        self._session = session
        self._transition_session(SessionStatus.INITIALIZING)

        world = self._world or WorldGenerator(self._generation_config).generate()
        self._runtime = {
            "execution_config": self._execution_config,
            "generation_config": self._generation_config,
            "personas": world.personas,
            "groups": world.groups,
            "memberships": world.memberships,
            "world_statistics": world.statistics,
            "scheduler": self._scheduler,
            "scenario_manager": self._scenario_manager,
            "conversation_manager": self._conversation_manager,
            "pipeline": self._pipeline,
            "event_bus": self._event_bus,
            "metrics": self._metrics,
            "resource_manager": self._resources,
            "checkpoint_store": self._checkpoints,
        }

        session.user_count = len(world.personas)
        session.group_count = len(world.groups)
        self._transition_session(SessionStatus.READY)
        _log.info("Session %s initialized (%d users, %d groups)", session.session_id, session.user_count, session.group_count)
        return session

    def start(self) -> SimulationSession:
        """Begin simulation execution."""
        session = self._require_session()
        self._transition_session(SessionStatus.RUNNING)
        session.start_time = datetime.utcnow()
        self._metrics.start_session()
        self._current_tick = SimulationTick.first(session.start_time, self._execution_config)
        self._paused = False
        self._stop_requested = False
        self._event_bus.publish(EventType.SIMULATION_STARTED.value, {"session_id": str(session.session_id)})
        _log.info("Session %s started", session.session_id)

        try:
            self._run_loop()
        except Exception as exc:  # noqa: BLE001
            self._transition_session(SessionStatus.FAILED)
            session.end_time = datetime.utcnow()
            session.statistics = self._build_statistics()
            self._metrics.end_session()
            self._event_bus.publish(
                EventType.SIMULATION_STOPPED.value,
                {"session_id": str(session.session_id), "reason": "failed", "error": str(exc)},
            )
            raise ExecutionError(str(exc)) from exc

        return session

    def pause(self) -> None:
        session = self._require_session()
        self._transition_session(SessionStatus.PAUSED)
        self._paused = True
        self._event_bus.publish(EventType.SIMULATION_PAUSED.value, {"session_id": str(session.session_id)})

    def resume(self) -> None:
        session = self._require_session()
        self._transition_session(SessionStatus.RUNNING)
        self._paused = False
        self._event_bus.publish(EventType.SIMULATION_STARTED.value, {"session_id": str(session.session_id), "resumed": True})

    def stop(self) -> None:
        self._stop_requested = True
        session = self._require_session()
        if session.status == SessionStatus.RUNNING:
            self._transition_session(SessionStatus.STOPPING)

    def shutdown(self) -> None:
        """Clean shutdown — stop if running and finalize session."""
        if self._session is None:
            return
        if self._session.status in {SessionStatus.RUNNING, SessionStatus.PAUSED}:
            self.stop()
            self._finalize_session(SessionStatus.CANCELLED)
        _log.info("Execution engine shut down")

    def run_single_tick(self) -> SimulationTick | None:
        """Execute one tick (for testing or manual stepping)."""
        session = self._require_session()
        if session.status not in {SessionStatus.RUNNING, SessionStatus.READY}:
            raise ExecutionError(f"Cannot run tick in status {session.status.value}.")
        if session.status == SessionStatus.READY:
            self._transition_session(SessionStatus.RUNNING)
            session.start_time = session.start_time or datetime.utcnow()
            self._metrics.start_session()
            self._current_tick = SimulationTick.first(session.start_time, self._execution_config)

        if self._current_tick is None:
            raise ExecutionError("Tick not initialized.")

        executed = self._current_tick
        self._execute_tick(executed)
        if executed.number >= self._execution_config.max_ticks:
            self._finalize_session(SessionStatus.COMPLETED)
            return executed

        self._current_tick = executed.advance(self._execution_config)
        return executed

    def get_statistics(self) -> dict[str, Any]:
        session = self._require_session()
        return self._build_statistics(session=session)

    def latest_checkpoint(self):
        session = self._require_session()
        return self._checkpoints.latest(session.session_id)

    def runtime_snapshot(self) -> dict[str, Any]:
        """Serializable runtime view for Threat Simulation console (simulator-only)."""
        personas = self._runtime.get("personas") or []
        groups = self._runtime.get("groups") or []
        events = self._runtime.get("message_events") or []
        results = self._runtime.get("pipeline_results") or []
        return {
            "personas": [
                p.to_dict() if hasattr(p, "to_dict") else p for p in personas[:500]
            ],
            "groups": [
                g.to_dict() if hasattr(g, "to_dict") else g for g in groups[:200]
            ],
            "message_events": [
                e.to_dict() if hasattr(e, "to_dict") else e for e in events
            ],
            "pipeline_results": [
                r.to_dict() if hasattr(r, "to_dict") else r for r in results
            ],
            "metrics": self._metrics.snapshot(),
            "event_bus_history": [
                {"type": t, "payload": p} for t, p in self._event_bus.history[-50:]
            ],
            "pipeline_stages": self._pipeline.stage_names,
            "current_tick": self._session.current_tick if self._session else 0,
        }

    @property
    def generation_config(self) -> GenerationConfig:
        return self._generation_config

    @property
    def execution_config(self) -> ExecutionConfig:
        return self._execution_config

    def _run_loop(self) -> None:
        session = self._require_session()
        while not self._stop_requested and self._current_tick is not None:
            if self._paused:
                break
            if self._current_tick.number > self._execution_config.max_ticks:
                break
            if self._resources.should_throttle():
                _log.warning("Resource throttle active — proceeding with reduced load")

            self._execute_tick(self._current_tick)
            session.current_tick = self._current_tick.number
            session.elapsed_simulated_seconds = self._current_tick.elapsed_simulated_seconds

            if self._current_tick.number >= self._execution_config.max_ticks:
                break
            self._current_tick = self._current_tick.advance(self._execution_config)

        if self._stop_requested:
            self._finalize_session(SessionStatus.CANCELLED)
        elif self._paused:
            pass
        else:
            self._finalize_session(SessionStatus.COMPLETED)

    def _execute_tick(self, tick: SimulationTick) -> None:
        session = self._require_session()
        for step in self._steps:
            try:
                step.execute(session=session, tick=tick, runtime=self._runtime)
            except Exception as exc:  # noqa: BLE001 — fault tolerance per step
                _log.error("Step %s failed on tick %d: %s", step.name, tick.number, exc)
                self._metrics.processing_errors += 1
        session.current_tick = tick.number
        session.elapsed_simulated_seconds = tick.elapsed_simulated_seconds

    def _finalize_session(self, status: SessionStatus) -> None:
        session = self._require_session()
        if session.status in TERMINAL_STATUSES:
            return
        self._transition_session(status)
        session.end_time = datetime.utcnow()
        session.statistics = self._build_statistics(session=session)
        self._metrics.end_session()
        event = (
            EventType.SIMULATION_COMPLETED.value
            if status == SessionStatus.COMPLETED
            else EventType.SIMULATION_STOPPED.value
        )
        self._event_bus.publish(event, {"session_id": str(session.session_id), "status": status.value})

    def _build_statistics(self, *, session: SimulationSession | None = None) -> dict[str, Any]:
        target = session or self._require_session()
        return {
            "session": target.to_dict(),
            "metrics": self._metrics.snapshot(),
            "pipeline_stages": self._pipeline.stage_names,
            "world": {
                "users": target.user_count,
                "groups": target.group_count,
            },
            "checkpoints": len(self._checkpoints.all_for_session(target.session_id)),
        }

    def _transition_session(self, target: SessionStatus) -> None:
        session = self._require_session()
        if session.is_terminal and target != session.status:
            raise SessionError("Session is immutable once completed.")
        assert_session_transition(session.status, target)
        session.status = target

    def _require_session(self) -> SimulationSession:
        if self._session is None:
            raise SessionError("No active session. Call initialize_session() first.")
        return self._session
