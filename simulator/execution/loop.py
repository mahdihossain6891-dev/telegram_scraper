"""Extensible simulation loop steps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from simulator.conversation.manager import ConversationManager
from simulator.execution.bridge import MessageEventConverter
from simulator.execution.config import ExecutionConfig
from simulator.execution.session import SimulationSession
from simulator.execution.tick import SimulationTick
from simulator.groups.profiles import Group
from simulator.metrics.engine import MetricsEngine
from simulator.personas.profiles import Persona
from simulator.pipeline.controller import PipelineController
from simulator.scheduler.manager import SchedulerManager
from simulator.scenario.manager import ScenarioManager


class BaseExecutionStep(ABC):
    name: str

    @abstractmethod
    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None: ...


class SchedulerStep(BaseExecutionStep):
    name = "scheduler"

    def __init__(self, scheduler: SchedulerManager) -> None:
        self._scheduler = scheduler

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        config: ExecutionConfig = runtime["execution_config"]
        personas: list[Persona] = runtime["personas"]
        groups: list[Group] = runtime["groups"]
        active_by_group: dict[str, list[Persona]] = {}
        for group in groups:
            active = self._scheduler.active_users_for_group(personas, group)
            active_by_group[str(group.id)] = active[: config.max_active_users]
        runtime["active_users_by_group"] = active_by_group
        runtime["metrics"].active_users = sum(len(v) for v in active_by_group.values())


class ScenarioStep(BaseExecutionStep):
    name = "scenario"

    def __init__(self, scenario_manager: ScenarioManager) -> None:
        self._scenario = scenario_manager

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        groups: list[Group] = runtime["groups"]
        active_by_group: dict[str, list[Persona]] = runtime["active_users_by_group"]
        scenario_contexts: dict[str, Any] = {}
        for group in groups:
            candidates = active_by_group.get(str(group.id), [])
            if len(candidates) < 2:
                continue
            ctx = self._scenario.build_context(group=group, candidates=candidates, when=tick.simulated_time)
            scenario_contexts[str(group.id)] = ctx
            runtime["metrics"].record_scenario(ctx.scenario.scenario_id)
        runtime["scenario_contexts"] = scenario_contexts


class ConversationStep(BaseExecutionStep):
    name = "conversation"

    def __init__(self, conversation_manager: ConversationManager) -> None:
        self._conversation = conversation_manager

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        config: ExecutionConfig = runtime["execution_config"]
        groups: list[Group] = runtime["groups"]
        personas: list[Persona] = runtime["personas"]
        events: list = []
        messages_generated = 0
        converter = runtime.get("message_converter")
        if converter is None:
            converter = MessageEventConverter(personas, groups)
            runtime["message_converter"] = converter

        for group in groups[: config.max_active_conversations]:
            if messages_generated >= config.max_messages_per_tick:
                break
            context = self._conversation.generate_conversation(personas, group)
            if context is None:
                continue
            for message in context.thread.messages:
                if messages_generated >= config.max_messages_per_tick:
                    break
                events.append(converter.convert(message))
                messages_generated += 1

        runtime["message_events"] = events
        runtime["metrics"].record_message_generated(messages_generated)
        runtime["metrics"].active_conversations = len(self._conversation.active_conversations)


class PipelineStep(BaseExecutionStep):
    name = "pipeline"

    def __init__(self, pipeline: PipelineController) -> None:
        self._pipeline = pipeline

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        events = runtime.get("message_events", [])
        results = []
        for event in events:
            result = self._pipeline.process(
                event,
                session_id=str(session.session_id),
                tick=tick.number,
            )
            results.append(result)
            runtime["metrics"].record_message_processed(
                stage_durations=result.context.stage_durations_ms,
                success=result.success,
            )
            runtime["metrics"].record_retry(result.context.retry_count)
            if result.context.alert:
                runtime["metrics"].record_alert()
            if result.context.relationships:
                runtime["metrics"].record_relationship_update(len(result.context.relationships))
            if result.context.behavior:
                runtime["metrics"].record_behavior_update()
        runtime["pipeline_results"] = results
        runtime["metrics"].record_tick(messages_processed=len(results))


class MetricsStep(BaseExecutionStep):
    name = "metrics"

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        resource_manager = runtime["resource_manager"]
        queue_size = len(runtime.get("message_events", []))
        rate = runtime["metrics"].pipeline_throughput_per_tick
        snapshot = resource_manager.snapshot(queue_size=queue_size, processing_rate=rate)
        runtime["metrics"].update_resource_snapshot(
            memory_mb=snapshot["memory_usage_mb"],
            cpu_percent=snapshot["cpu_usage_percent"],
        )
        runtime["event_bus"].publish(
            "MetricsUpdated",
            {"tick": tick.number, "metrics": runtime["metrics"].snapshot()},
        )


class CheckpointStep(BaseExecutionStep):
    name = "checkpoint"

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None:
        config: ExecutionConfig = runtime["execution_config"]
        if tick.number % config.checkpoint_frequency_ticks != 0:
            return
        store = runtime["checkpoint_store"]
        checkpoint = store.create(
            session_id=session.session_id,
            current_tick=tick.number,
            scheduler_state={"simulated_time": tick.simulated_time.isoformat()},
            conversation_state={
                "active": len(runtime["conversation_manager"].active_conversations),
                "closed": len(runtime["conversation_manager"].closed_conversations),
            },
            scenario_state=runtime["scenario_manager"].get_statistics().to_dict()
            if hasattr(runtime["scenario_manager"].get_statistics(), "to_dict")
            else {},
            metrics=runtime["metrics"].snapshot(),
            statistics=dict(session.statistics),
            session_metadata=session.to_dict(),
        )
        store.save(checkpoint)
        runtime["last_checkpoint"] = checkpoint
