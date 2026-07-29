"""Pipeline controller — executes stages and publishes results."""

from __future__ import annotations

from simulator.events.bus import EventBus
from simulator.events.types import EventType
from simulator.pipeline.interfaces import PipelineStage
from simulator.logger import get_prefixed_logger
from simulator.models import MessageEvent
from simulator.pipeline.context import ProcessingContext
from simulator.pipeline.result import ProcessingResult

_log = get_prefixed_logger("pipeline", name="controller")


class PipelineController:
    """Receives MessageEvents and runs them through ordered pipeline stages."""

    def __init__(
        self,
        stages: list[PipelineStage],
        *,
        event_bus: EventBus | None = None,
        retry_count: int = 2,
    ) -> None:
        self._stages = list(stages)
        self._event_bus = event_bus or EventBus()
        self._retry_count = retry_count

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def stage_names(self) -> list[str]:
        return [stage.name for stage in self._stages]

    def process(self, event: MessageEvent, *, session_id: str, tick: int) -> ProcessingResult:
        context = ProcessingContext(event=event, session_id=session_id, tick=tick)
        failed: list[str] = []

        for stage in self._stages:
            attempts = 0
            while True:
                attempts += 1
                try:
                    context = stage.process(context)
                    break
                except Exception as exc:  # noqa: BLE001 — fault tolerance boundary
                    context.stage_errors[stage.name] = str(exc)
                    _log.error("Stage %s failed: %s", stage.name, exc)
                    if attempts > self._retry_count:
                        failed.append(stage.name)
                        break
                    context.retry_count += 1

        success = not failed
        if context.keywords:
            self._event_bus.publish(
                EventType.KEYWORD_DETECTED.value,
                {"keywords": context.keywords, "message_id": event.message_id},
            )
        if context.risk_score > 0:
            self._event_bus.publish(
                EventType.RISK_CALCULATED.value,
                {"risk_score": context.risk_score, "level": context.risk_level},
            )
        if context.alert:
            self._event_bus.publish(EventType.ALERT_GENERATED.value, dict(context.alert))
        self._event_bus.publish(
            EventType.MESSAGE_PROCESSED.value,
            {"message_id": event.message_id, "success": success, "tick": tick},
        )

        return ProcessingResult(context=context, success=success, failed_stages=tuple(failed))
