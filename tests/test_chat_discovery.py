"""Tests for chat discovery module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, Chat, User

from chat_discovery import (
    ChatDiscovery,
    ChatDiscoveryError,
    ChatNotFoundError,
    DiscoveredChat,
    classify_chat_type,
)


def _run(coro):
    return asyncio.run(coro)


def _user(user_id: int = 1) -> User:
    return User(id=user_id, access_hash=0, first_name="Test")


def _chat(chat_id: int, title: str) -> Chat:
    return Chat(
        id=chat_id,
        title=title,
        photo=None,
        participants_count=1,
        date=datetime.now(timezone.utc),
        version=0,
    )


def _channel(
    channel_id: int,
    title: str,
    *,
    broadcast: bool = False,
    megagroup: bool = False,
) -> Channel:
    return Channel(
        id=channel_id,
        title=title,
        photo=None,
        date=datetime.now(timezone.utc),
        broadcast=broadcast,
        megagroup=megagroup,
    )


def _dialog(dialog_id: int, name: str, entity: object) -> MagicMock:
    dialog = MagicMock()
    dialog.id = dialog_id
    dialog.name = name
    dialog.entity = entity
    return dialog


def _iter_dialogs_mock(*dialogs: MagicMock) -> MagicMock:
    async def _async_dialogs():
        for dialog in dialogs:
            yield dialog

    return MagicMock(return_value=_async_dialogs())


def _client_with_dialogs(*dialogs: MagicMock) -> MagicMock:
    client = MagicMock()
    client.is_user_authorized = AsyncMock(return_value=True)
    client.iter_dialogs = _iter_dialogs_mock(*dialogs)
    return client


class TestClassifyChatType:
    """Tests for Telethon entity classification."""

    def test_user_is_private_chat(self) -> None:
        assert classify_chat_type(_user()) == "private chat"

    def test_chat_is_group(self) -> None:
        assert classify_chat_type(_chat(2, "Group")) == "group"

    def test_channel_broadcast_is_channel(self) -> None:
        assert classify_chat_type(_channel(3, "News", broadcast=True)) == "channel"

    def test_channel_megagroup_is_supergroup(self) -> None:
        assert classify_chat_type(_channel(4, "Team", megagroup=True)) == "supergroup"


class TestFormatAndDisplay:
    """Tests for chat formatting helpers."""

    def test_format_chat_line_includes_required_fields(self) -> None:
        chat = DiscoveredChat(
            chat_id=-1001234567890,
            name="Intel Channel",
            chat_type="channel",
            index=1,
            username="intel",
        )
        line = ChatDiscovery.format_chat_line(chat)
        assert "ID: -1001234567890" in line
        assert "Type: channel" in line
        assert "Name: Intel Channel" in line
        assert "@intel" in line


class TestSelectChat:
    """Tests for chat selection by ID or index."""

    @staticmethod
    def _sample_chats() -> list[DiscoveredChat]:
        return [
            DiscoveredChat(101, "Alice", "private chat", 1),
            DiscoveredChat(-100222, "Ops Group", "supergroup", 2),
            DiscoveredChat(-100333, "News", "channel", 3),
        ]

    def test_select_by_index(self) -> None:
        selected = ChatDiscovery.select_chat(self._sample_chats(), "2")
        assert selected.name == "Ops Group"
        assert selected.chat_id == -100222

    def test_select_by_chat_id(self) -> None:
        selected = ChatDiscovery.select_chat(self._sample_chats(), "-100333")
        assert selected.name == "News"
        assert selected.index == 3

    def test_select_prefers_chat_id_over_index_when_both_match(self) -> None:
        chats = [
            DiscoveredChat(2, "By ID", "group", 1),
            DiscoveredChat(999, "By Index", "group", 2),
        ]
        selected = ChatDiscovery.select_chat(chats, "2")
        assert selected.name == "By ID"

    def test_select_empty_list_raises(self) -> None:
        with pytest.raises(ChatNotFoundError, match="No chats available"):
            ChatDiscovery.select_chat([], "1")

    def test_select_invalid_value_raises(self) -> None:
        with pytest.raises(ChatNotFoundError, match="Invalid selection"):
            ChatDiscovery.select_chat(self._sample_chats(), "abc")

    def test_select_out_of_range_raises(self) -> None:
        with pytest.raises(ChatNotFoundError, match="No chat matched"):
            ChatDiscovery.select_chat(self._sample_chats(), "99")


class TestFetchChats:
    """Tests for retrieving dialogs from Telethon."""

    def test_fetch_chats_returns_classified_dialogs(self) -> None:
        client = _client_with_dialogs(
            _dialog(1001, "Alice", _user(1001)),
            _dialog(-1002002, "Team", _channel(2002, "Team", megagroup=True)),
        )

        discovery = ChatDiscovery(client)
        chats = _run(discovery.fetch_chats())

        assert len(chats) == 2
        assert chats[0].chat_type == "private chat"
        assert chats[0].index == 1
        assert chats[1].chat_type == "supergroup"
        assert chats[1].name == "Team"

    def test_fetch_chats_requires_authorization(self) -> None:
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=False)

        discovery = ChatDiscovery(client)
        with pytest.raises(ChatDiscoveryError, match="not authorized"):
            _run(discovery.fetch_chats())

    def test_fetch_chats_wraps_rpc_errors(self) -> None:
        client = MagicMock()
        client.is_user_authorized = AsyncMock(return_value=True)

        async def _failing_dialogs():
            raise FloodWaitError(request=None, capture=30)
            yield  # pragma: no cover

        client.iter_dialogs = MagicMock(return_value=_failing_dialogs())

        discovery = ChatDiscovery(client)
        with pytest.raises(ChatDiscoveryError, match="Failed to retrieve chats"):
            _run(discovery.fetch_chats())


class TestDiscoverAndSelect:
    """Tests for combined discovery and selection flow."""

    def test_discover_and_select_by_index(self) -> None:
        from chat_discovery import discover_and_select

        client = _client_with_dialogs(
            _dialog(42, "Test Chat", _chat(42, "Test Chat")),
        )

        chats, selected = _run(discover_and_select(client, selection="1"))

        assert len(chats) == 1
        assert selected is not None
        assert selected.chat_id == 42

    def test_discover_without_selection(self) -> None:
        from chat_discovery import discover_and_select

        client = _client_with_dialogs(
            _dialog(7, "Solo", _user(7)),
        )

        chats, selected = _run(discover_and_select(client))

        assert len(chats) == 1
        assert selected is None
