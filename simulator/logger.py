"""Simulator logging — domain-prefixed for easy filtering.

Prefixes:
    [SIMULATION]  — simulator control plane
    [ENVIRONMENT] — environment switching / isolation
    [SOURCE]      — message source adapters
    [PERSONA]     — persona generation and management
    [GROUP]       — group generation and membership
    [GENERATOR]   — world generation orchestration
    [CONVERSATION] — conversation lifecycle
    [SCHEDULER]   — activity scheduling
    [REPLY]       — reply generation
    [THREAD]      — thread lifecycle
    [SCENARIO]    — scenario selection and lifecycle
    [EXECUTION]   — simulation execution engine
    [PIPELINE]    — pipeline controller and stages
    [EVENT]       — event bus notifications
    [METRICS]     — metrics collection
"""

from __future__ import annotations

import logging
from typing import Any

from simulator.constants import (
    LOG_PREFIX_CONVERSATION,
    LOG_PREFIX_EVENT,
    LOG_PREFIX_EXECUTION,
    LOG_NAMESPACE,
    LOG_PREFIX_ENVIRONMENT,
    LOG_PREFIX_GENERATOR,
    LOG_PREFIX_GROUP,
    LOG_PREFIX_METRICS,
    LOG_PREFIX_PERSONA,
    LOG_PREFIX_PIPELINE,
    LOG_PREFIX_REPLY,
    LOG_PREFIX_SCENARIO,
    LOG_PREFIX_SCHEDULER,
    LOG_PREFIX_SIMULATION,
    LOG_PREFIX_SOURCE,
    LOG_PREFIX_THREAD,
)


class _PrefixedLogAdapter(logging.LoggerAdapter):
    """Prepends a domain prefix to every log message."""

    def __init__(self, logger: logging.Logger, prefix: str) -> None:
        super().__init__(logger, {"prefix": prefix})
        self._prefix = prefix

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        return f"{self._prefix} {msg}", kwargs


def get_prefixed_logger(
    domain: str,
    *,
    name: str | None = None,
) -> logging.LoggerAdapter:
    """Return a logger with an explicit domain prefix.

    Args:
        domain: One of ``simulation``, ``environment``, ``source``, ``persona``,
            ``group``, ``generator``, ``conversation``, ``scheduler``,
            ``reply``, ``thread``, ``scenario``, ``execution``,
            ``pipeline``, ``event``, ``metrics``.
        name: Optional submodule suffix.
    """
    prefix_map = {
        "simulation": LOG_PREFIX_SIMULATION,
        "environment": LOG_PREFIX_ENVIRONMENT,
        "source": LOG_PREFIX_SOURCE,
        "persona": LOG_PREFIX_PERSONA,
        "group": LOG_PREFIX_GROUP,
        "generator": LOG_PREFIX_GENERATOR,
        "conversation": LOG_PREFIX_CONVERSATION,
        "scheduler": LOG_PREFIX_SCHEDULER,
        "reply": LOG_PREFIX_REPLY,
        "thread": LOG_PREFIX_THREAD,
        "scenario": LOG_PREFIX_SCENARIO,
        "execution": LOG_PREFIX_EXECUTION,
        "pipeline": LOG_PREFIX_PIPELINE,
        "event": LOG_PREFIX_EVENT,
        "metrics": LOG_PREFIX_METRICS,
    }
    prefix = prefix_map.get(domain, LOG_PREFIX_SIMULATION)
    logger_name = LOG_NAMESPACE if not name else f"{LOG_NAMESPACE}.{name}"
    return _PrefixedLogAdapter(logging.getLogger(logger_name), prefix)


def get_simulator_logger(name: str | None = None) -> logging.LoggerAdapter:
    """Return a ``[SIMULATION]`` logger (Phase 1 compatible alias)."""
    return get_prefixed_logger("simulation", name=name)
