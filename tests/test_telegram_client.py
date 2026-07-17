"""Tests for Telegram client authentication module."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError

import telegram_client
from telegram_client import (
    AuthCallbacks,
    TelegramAuthError,
    TelegramClientManager,
    _mask_phone,
    create_interactive_callbacks,
    session_file_exists,
)


def _run(coro):
    """Run an async coroutine in a sync test."""
    return asyncio.run(coro)


class TestMaskPhone:
    """Tests for phone masking helper."""

    def test_masks_middle_digits(self) -> None:
        assert _mask_phone("+1234567890") == "+12***90"

    def test_short_phone_fully_masked(self) -> None:
        assert _mask_phone("1234") == "****"


class TestSessionFileExists:
    """Tests for session file detection."""

    def test_returns_false_when_missing(self, tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_project)
        sys.path.insert(0, str(tmp_project))
        try:
            import config as config_module

            importlib = __import__("importlib")
            config_module = importlib.reload(config_module)
            settings = config_module.load_settings()
            assert session_file_exists(settings) is False
        finally:
            sys.path.remove(str(tmp_project))

    def test_returns_true_when_session_present(
        self,
        tmp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_project)
        sys.path.insert(0, str(tmp_project))
        try:
            import importlib

            import config as config_module

            config_module = importlib.reload(config_module)
            settings = config_module.load_settings()
            session_path = settings.session_path.with_suffix(".session")
            session_path.write_text("fake session", encoding="utf-8")
            assert session_file_exists(settings) is True
        finally:
            sys.path.remove(str(tmp_project))


class TestCreateInteractiveCallbacks:
    """Tests for interactive callback factory."""

    def test_uses_env_phone_when_set(self, env_vars: dict[str, str]) -> None:
        import config as config_module
        import importlib

        importlib.reload(config_module)
        settings = config_module.load_settings()
        callbacks = create_interactive_callbacks(settings)

        assert callbacks.phone is not None
        assert _run(_resolve_phone(callbacks, settings)) == "+10000000000"

    def test_prompts_for_phone_when_not_in_env(
        self,
        env_vars: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import importlib

        import config as config_module

        monkeypatch.setenv("TELEGRAM_PHONE", "")
        config_module = importlib.reload(config_module)
        settings = config_module.load_settings()
        callbacks = create_interactive_callbacks(settings)
        monkeypatch.setattr("builtins.input", lambda _prompt: "+19998887777")

        assert callbacks.phone is not None
        assert callbacks.phone() == "+19998887777"


async def _resolve_phone(callbacks: AuthCallbacks, settings) -> str:
    """Helper mirroring manager phone resolution for callback tests."""
    manager = TelegramClientManager(settings, callbacks)
    return await manager.resolve_phone()


class TestTelegramClientManager:
    """Tests for TelegramClientManager."""

    @staticmethod
    def _settings():
        import config as config_module

        return config_module.load_settings()

    def test_create_client_uses_session_path(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        manager = TelegramClientManager(settings, AuthCallbacks(code=lambda: "00000"))

        with patch.object(telegram_client, "TelegramClient") as mock_client_cls:
            manager.create_client()
            mock_client_cls.assert_called_once_with(
                str(settings.session_path),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )

    def test_authenticate_skips_when_already_authorized(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        manager = TelegramClientManager(settings, AuthCallbacks(code=lambda: "00000"))
        client = AsyncMock()
        client.is_user_authorized.return_value = True
        client.get_me.return_value = MagicMock(username="testuser", first_name="Test", id=1)

        _run(manager.authenticate(client))

        client.send_code_request.assert_not_called()
        client.sign_in.assert_not_called()

    def test_authenticate_signs_in_with_code(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        callbacks = AuthCallbacks(phone=lambda: "+10000000000", code=lambda: "12345")
        manager = TelegramClientManager(settings, callbacks)
        client = AsyncMock()
        client.is_user_authorized.side_effect = [False, True]
        client.get_me.return_value = MagicMock(username="alice", first_name="Alice", id=42)

        _run(manager.authenticate(client))

        client.send_code_request.assert_awaited_once_with("+10000000000")
        client.sign_in.assert_awaited_once_with("+10000000000", "12345")

    def test_authenticate_handles_two_factor_password(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        callbacks = AuthCallbacks(
            phone=lambda: "+10000000000",
            code=lambda: "12345",
            password=lambda: "secret2fa",
        )
        manager = TelegramClientManager(settings, callbacks)
        client = AsyncMock()
        client.is_user_authorized.side_effect = [False, True]
        client.sign_in.side_effect = [SessionPasswordNeededError(request=None), None]
        client.get_me.return_value = MagicMock(username="bob", first_name="Bob", id=7)

        _run(manager.authenticate(client))

        assert client.sign_in.await_count == 2
        client.sign_in.assert_any_await("+10000000000", "12345")
        client.sign_in.assert_any_await(password="secret2fa")

    def test_authenticate_raises_on_invalid_code(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        callbacks = AuthCallbacks(phone=lambda: "+10000000000", code=lambda: "bad")
        manager = TelegramClientManager(settings, callbacks)
        client = AsyncMock()
        client.is_user_authorized.return_value = False
        client.sign_in.side_effect = PhoneCodeInvalidError(request=None)

        with pytest.raises(TelegramAuthError, match="Invalid verification code"):
            _run(manager.authenticate(client))

    def test_authenticate_raises_when_phone_missing(self, env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        import config as config_module

        monkeypatch.setenv("TELEGRAM_PHONE", "")
        importlib.reload(config_module)
        settings = config_module.load_settings()
        manager = TelegramClientManager(settings, AuthCallbacks(code=lambda: "12345"))
        client = AsyncMock()
        client.is_user_authorized.return_value = False

        with pytest.raises(TelegramAuthError, match="Phone number is required"):
            _run(manager.authenticate(client))

    def test_authenticate_raises_when_2fa_password_missing(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        manager = TelegramClientManager(settings, AuthCallbacks(phone=lambda: "+10000000000", code=lambda: "12345"))
        client = AsyncMock()
        client.is_user_authorized.return_value = False
        client.sign_in.side_effect = SessionPasswordNeededError(request=None)

        with pytest.raises(TelegramAuthError, match="Two-factor authentication"):
            _run(manager.authenticate(client))

    def test_start_connects_and_authenticates(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        manager = TelegramClientManager(settings, AuthCallbacks(code=lambda: "00000"))
        client = AsyncMock()
        client.is_connected = MagicMock(return_value=False)
        client.is_user_authorized.return_value = True
        client.get_me.return_value = MagicMock(username="user", first_name="User", id=3)

        with patch.object(manager, "create_client", return_value=client):
            result = _run(manager.start())

        assert result is client
        client.connect.assert_awaited_once()

    def test_stop_disconnects_active_client(self, env_vars: dict[str, str]) -> None:
        settings = self._settings()
        manager = TelegramClientManager(settings, AuthCallbacks(code=lambda: "00000"))
        client = AsyncMock()
        client.is_connected = MagicMock(return_value=True)

        _run(manager.stop(client))

        client.disconnect.assert_awaited_once()


class TestAuthenticateHelper:
    """Tests for module-level authenticate()."""

    def test_authenticate_uses_manager(self, env_vars: dict[str, str]) -> None:
        mock_client = AsyncMock()

        async def _test() -> None:
            with patch.object(
                telegram_client.TelegramClientManager,
                "start",
                AsyncMock(return_value=mock_client),
            ) as mock_start:
                with patch.object(telegram_client, "ensure_directories") as mock_ensure:
                    mock_ensure.return_value = telegram_client.load_settings()
                    result = await telegram_client.authenticate()
                    assert result is mock_client
                    mock_start.assert_awaited_once()

        _run(_test())
