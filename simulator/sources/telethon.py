"""Telethon message source — placeholder (no Telethon integration in Phase 2)."""

from __future__ import annotations

from simulator.enums import EnvironmentType, MessageSourceKind
from simulator.logger import get_prefixed_logger
from simulator.sources.base import MessageSource

_log = get_prefixed_logger("source", name="telethon")


class TelethonSource(MessageSource):
    """Live Telegram ingestion via Telethon.

    Phase 2: dormant placeholder. Production ``message_scraper.py`` is unchanged.
    Telethon becomes active only when the application runs in LIVE mode and this
    source is selected by ``EnvironmentService``.
    """

    def __init__(self) -> None:
        self._active = False
        _log.debug("TelethonSource placeholder initialized (inactive)")

    @property
    def environment(self) -> EnvironmentType:
        return EnvironmentType.LIVE

    @property
    def source_kind(self) -> MessageSourceKind:
        return MessageSourceKind.TELETHON

    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        """Mark source active when LIVE environment is selected."""
        self._active = True
        _log.info("TelethonSource marked active (placeholder — no Telethon session)")

    def deactivate(self) -> None:
        self._active = False
        _log.info("TelethonSource deactivated")
