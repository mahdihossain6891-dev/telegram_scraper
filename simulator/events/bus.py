"""Event Bus — notification only, no business logic."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from simulator.logger import get_prefixed_logger

_log = get_prefixed_logger("event", name="bus")

EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Broadcasts completed events to subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[tuple[str, dict[str, Any]]] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        record = dict(payload)
        self._history.append((event_type, record))
        _log.debug("Published %s", event_type)
        for handler in self._subscribers.get(event_type, []):
            handler(record)
        for handler in self._subscribers.get("*", []):
            handler({"event_type": event_type, **record})

    @property
    def history(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
