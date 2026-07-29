"""Tests for monitored chat resolution."""

from __future__ import annotations

from chat_discovery import DiscoveredChat
from models import Chat
from scrape_jobs.runner import resolve_monitored_chats


class _FakeSession:
    def __init__(self, chats: list[Chat]) -> None:
        self._chats = chats

    def list_chats(self) -> list[Chat]:
        return self._chats


def _discovered() -> list[DiscoveredChat]:
    return [
        DiscoveredChat(1, "Ops Channel", "channel", 1, username="ops"),
        DiscoveredChat(2, "Private DM", "private chat", 2),
        DiscoveredChat(3, "Investigation Group", "supergroup", 3),
    ]


def test_resolve_monitored_chats_uses_db_registry() -> None:
    session = _FakeSession(
        [
            Chat(id=1, title="Ops Channel", username="ops", chat_type="channel"),
            Chat(id=3, title="Investigation Group", username=None, chat_type="supergroup"),
        ]
    )
    matched, scope = resolve_monitored_chats(session, _discovered())
    assert scope == "monitored_db"
    assert {chat.chat_id for chat in matched} == {1, 3}


def test_resolve_monitored_chats_excludes_private_by_default() -> None:
    session = _FakeSession(
        [Chat(id=2, title="Private DM", username=None, chat_type="private chat")]
    )
    matched, _scope = resolve_monitored_chats(session, _discovered(), include_private=False)
    assert matched == []
