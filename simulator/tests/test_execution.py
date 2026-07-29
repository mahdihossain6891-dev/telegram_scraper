"""Tests for Phase 7 Simulation Execution Engine."""

from __future__ import annotations

import random

import pytest

from simulator.events.types import EventType
from simulator.exceptions import InvalidSessionTransition
from simulator.execution.config import ExecutionConfig
from simulator.execution.engine import SimulationExecutionEngine
from simulator.execution.labels import SessionStatus
from simulator.execution.session import SimulationSession
from simulator.execution.transitions import assert_session_transition
from simulator.generation_config import GenerationConfig
from simulator.pipeline.context import ProcessingContext
from simulator.pipeline.controller import PipelineController
from simulator.pipeline.stages import (
    KeywordStage,
    NormalizationStage,
    RiskStage,
    ValidationStage,
    default_pipeline_stages,
)
from simulator.enums import EnvironmentType
from simulator.models import MessageEvent
from datetime import datetime


def _small_engine(*, max_ticks: int = 3, max_messages: int = 2) -> SimulationExecutionEngine:
    return SimulationExecutionEngine(
        execution_config=ExecutionConfig(
            max_ticks=max_ticks,
            max_messages_per_tick=max_messages,
            checkpoint_frequency_ticks=1,
            max_active_conversations=2,
        ),
        generation_config=GenerationConfig(
            user_count=40,
            group_count=4,
            random_seed=7,
            maximum_concurrent_conversations=2,
            max_thread_messages=12,
            average_conversation_length=8,
        ),
        simulation_name="test-run",
    )


class TestSessionLifecycle:
    def test_valid_transitions(self) -> None:
        assert_session_transition(SessionStatus.INITIALIZING, SessionStatus.READY)
        assert_session_transition(SessionStatus.READY, SessionStatus.RUNNING)
        assert_session_transition(SessionStatus.RUNNING, SessionStatus.PAUSED)
        assert_session_transition(SessionStatus.PAUSED, SessionStatus.RUNNING)
        assert_session_transition(SessionStatus.RUNNING, SessionStatus.COMPLETED)

    def test_illegal_transition_raises(self) -> None:
        with pytest.raises(InvalidSessionTransition):
            assert_session_transition(SessionStatus.COMPLETED, SessionStatus.RUNNING)

    def test_session_initialize_and_complete(self) -> None:
        engine = _small_engine(max_ticks=2)
        session = engine.initialize_session()
        assert session.status == SessionStatus.READY
        assert session.user_count > 0
        assert session.group_count > 0

        engine.start()
        assert engine.session is not None
        assert engine.session.status == SessionStatus.COMPLETED
        assert engine.session.end_time is not None
        assert engine.session.statistics["metrics"]["messages_processed"] >= 0


class TestTickAdvancement:
    def test_single_tick_stepping(self) -> None:
        engine = _small_engine(max_ticks=5)
        engine.initialize_session()
        tick = engine.run_single_tick()
        assert tick is not None
        assert tick.number == 1
        assert engine.session is not None
        assert engine.session.current_tick == 1

    def test_elapsed_time_advances(self) -> None:
        engine = _small_engine(max_ticks=3)
        engine.initialize_session()
        engine.run_single_tick()
        engine.run_single_tick()
        assert engine.session.elapsed_simulated_seconds > 0


class TestPipelineExecution:
    def _event(self, text: str) -> MessageEvent:
        return MessageEvent(
            message_id=1,
            chat_id=-1001,
            sender_id=9001,
            timestamp=datetime(2026, 1, 1, 10, 0, 0),
            text=text,
            environment=EnvironmentType.SIMULATION,
        )

    def test_pipeline_ordering(self) -> None:
        controller = PipelineController(default_pipeline_stages())
        names = controller.stage_names
        assert names.index("validation") < names.index("normalization")
        assert names.index("normalization") < names.index("keyword")
        assert names.index("keyword") < names.index("risk")
        assert names.index("risk") < names.index("alert")
        assert names.index("alert") < names.index("persistence")

    def test_context_enrichment(self) -> None:
        controller = PipelineController(
            [ValidationStage(), NormalizationStage(), KeywordStage(), RiskStage()]
        )
        result = controller.process(
            self._event("URGENT transfer needed for crypto package"),
            session_id="sess-1",
            tick=1,
        )
        ctx = result.context
        assert ctx.normalized_text
        assert "urgent" in ctx.keywords
        assert ctx.risk_score > 0
        assert "validation" in ctx.stage_durations_ms

    def test_fault_recovery_continues(self) -> None:
        class FailingStage(ValidationStage):
            name = "validation"

            def _run(self, context: ProcessingContext) -> ProcessingContext:
                raise RuntimeError("boom")

        controller = PipelineController(
            [FailingStage(), NormalizationStage()],
            retry_count=0,
        )
        result = controller.process(self._event("hello"), session_id="s", tick=1)
        assert result.success is False
        assert "validation" in result.failed_stages


class TestEventBus:
    def test_pipeline_publishes_events(self) -> None:
        from simulator.conversation.manager import ConversationManager
        from simulator.conversation.templates import (
            ConversationLength,
            ConversationScenario,
            ConversationType,
            DefaultScenarioProvider,
            ScenarioSeed,
        )

        class FixedScenarioProvider(DefaultScenarioProvider):
            def next_scenario(self, *, group, participants, rng: random.Random) -> ScenarioSeed:
                return ScenarioSeed(
                    conversation=ConversationScenario(
                        topic="docker",
                        conversation_type=ConversationType.QUESTION,
                        opener="Anyone using Docker Desktop lately?",
                        keywords=("docker", "containers"),
                        desired_length=ConversationLength.MEDIUM,
                    ),
                    scenario_id="programming",
                )

        cfg = GenerationConfig(
            user_count=40,
            group_count=4,
            random_seed=7,
            max_thread_messages=12,
            average_conversation_length=8,
        )
        conversation_manager = ConversationManager(cfg, scenario_provider=FixedScenarioProvider())
        engine = SimulationExecutionEngine(
            execution_config=ExecutionConfig(max_ticks=1, max_messages_per_tick=3, checkpoint_frequency_ticks=1),
            generation_config=cfg,
            conversation_manager=conversation_manager,
            simulation_name="event-bus-test",
        )
        received: list[str] = []
        engine.event_bus.subscribe(EventType.MESSAGE_PROCESSED.value, lambda p: received.append(str(p["message_id"])))
        engine.initialize_session()
        engine.start()
        assert received


class TestMetricsAndCheckpoints:
    def test_metrics_collected(self) -> None:
        engine = _small_engine(max_ticks=2)
        engine.initialize_session()
        engine.start()
        metrics = engine.metrics.snapshot()
        assert metrics["ticks_completed"] >= 1
        assert "messages_generated" in metrics

    def test_checkpoint_created(self) -> None:
        engine = _small_engine(max_ticks=2)
        engine.initialize_session()
        engine.start()
        checkpoint = engine.latest_checkpoint()
        assert checkpoint is not None
        assert checkpoint.current_tick >= 1
        assert checkpoint.metrics


class TestPauseStop:
    def test_pause_after_start(self) -> None:
        engine = _small_engine(max_ticks=20)
        engine.initialize_session()
        engine._transition_session(SessionStatus.RUNNING)
        engine._session.start_time = datetime.utcnow()
        from simulator.execution.tick import SimulationTick

        engine._metrics.start_session()
        engine._current_tick = SimulationTick.first(engine._session.start_time, engine._execution_config)
        engine.pause()
        assert engine.session.status == SessionStatus.PAUSED

    def test_completed_session_immutable(self) -> None:
        from simulator.exceptions import SessionError

        engine = _small_engine(max_ticks=1)
        engine.initialize_session()
        engine.start()
        with pytest.raises(SessionError):
            engine._transition_session(SessionStatus.RUNNING)
