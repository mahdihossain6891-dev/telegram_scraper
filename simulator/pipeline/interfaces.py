"""Pipeline interfaces for dependency injection."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from simulator.models import MessageEvent
from simulator.pipeline.context import ProcessingContext
from simulator.pipeline.result import ProcessingResult


@runtime_checkable
class PipelineStage(Protocol):
    """One deterministic processing stage."""

    name: str

    def process(self, context: ProcessingContext) -> ProcessingContext: ...


@runtime_checkable
class PipelineControllerProtocol(Protocol):
    """Processes MessageEvents through ordered stages."""

    def process(self, event: MessageEvent, *, session_id: str, tick: int) -> ProcessingResult: ...
