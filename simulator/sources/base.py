"""Message source abstraction — pipeline-agnostic event producers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from simulator.enums import EnvironmentType, MessageSourceKind
from simulator.models.message_event import MessageEvent


class MessageSource(ABC):
    """Produces ``MessageEvent`` objects for the intelligence pipeline.

    Implementations must not expose Telethon or simulator internals to
    downstream consumers.
    """

    @property
    @abstractmethod
    def environment(self) -> EnvironmentType:
        """Environment this source belongs to."""

    @property
    @abstractmethod
    def source_kind(self) -> MessageSourceKind:
        """Discriminator for logging and diagnostics only."""

    @abstractmethod
    def is_active(self) -> bool:
        """Whether this source is currently producing events."""

    def poll(self) -> list[MessageEvent]:
        """Return pending events (non-blocking). Placeholders return empty."""
        return list(self.iter_events())

    def iter_events(self) -> Iterator[MessageEvent]:
        """Yield pending events. Default: none."""
        return iter(())

    def describe(self) -> dict[str, object]:
        """Serializable metadata for status endpoints."""
        return {
            "environment": self.environment.value,
            "source_kind": self.source_kind.value,
            "active": self.is_active(),
        }
