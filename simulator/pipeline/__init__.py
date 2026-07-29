"""Pipeline processing package."""

from simulator.pipeline.context import ProcessingContext
from simulator.pipeline.result import ProcessingResult
from simulator.pipeline.stages import default_pipeline_stages

__all__ = [
    "ProcessingContext",
    "ProcessingResult",
    "default_pipeline_stages",
]


def __getattr__(name: str):
    if name == "PipelineController":
        from simulator.pipeline.controller import PipelineController

        return PipelineController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
