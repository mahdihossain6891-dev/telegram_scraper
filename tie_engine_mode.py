"""Threat Intelligence Engine (TIE) enable/disable mode for Threat Console.

When disabled, Console uses its built-in keyword/risk scrape analyser only.
When enabled, scrape completion forwards flagged messages to TIE for processing.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, load_settings

logger = logging.getLogger("tie_engine_mode")

_STATE_PATH = PROJECT_ROOT / "data" / "tie_engine_mode.json"


def _default_enabled() -> bool:
    raw = os.getenv("TIE_ENGINE_ENABLED", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Default OFF so Console built-in analyser remains the primary path
    return False


def _read_state() -> dict[str, Any]:
    if not _STATE_PATH.is_file():
        return {"enabled": _default_enabled(), "updated_at": None}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return {
            "enabled": bool(data.get("enabled", _default_enabled())),
            "updated_at": data.get("updated_at"),
        }
    except Exception:
        logger.exception("tie_engine_mode_read_failed")
        return {"enabled": _default_enabled(), "updated_at": None}


def _write_state(enabled: bool) -> dict[str, Any]:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": bool(enabled),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def get_tie_engine_mode() -> dict[str, Any]:
    state = _read_state()
    return {
        "enabled": bool(state["enabled"]),
        "updated_at": state.get("updated_at"),
        "analyser": "tie" if state["enabled"] else "console_builtin",
        "description": (
            "TIE processes scrape intelligence"
            if state["enabled"]
            else "Threat Console built-in scrape analyser"
        ),
    }


def set_tie_engine_mode(enabled: bool) -> dict[str, Any]:
    state = _write_state(bool(enabled))
    logger.info("tie_engine_mode enabled=%s", state["enabled"])
    return get_tie_engine_mode()


def is_tie_engine_enabled() -> bool:
    return bool(_read_state().get("enabled"))


def _tie_base_url() -> str:
    return (
        os.getenv("TIE_API_URL")
        or os.getenv("THREAT_INTELLIGENCE_ENGINE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _tie_auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = (
        os.getenv("TIE_API_KEY")
        or os.getenv("THREAT_INTELLIGENCE_API_KEY")
        or os.getenv("SERVICE_API_KEY_ADMIN")
        or ""
    ).strip()
    bearer = os.getenv("TIE_BEARER_TOKEN", "").strip()
    if api_key:
        headers["X-API-Key"] = api_key
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def forward_flagged_messages_to_tie(*, limit: int = 200) -> dict[str, Any]:
    """
    After scrape: if TIE engine is enabled, POST recent flagged messages to TIE batches.

    Non-fatal — Console scrape results always remain in Console Mongo.
    """
    if not is_tie_engine_enabled():
        return {"skipped": True, "reason": "tie_engine_disabled"}

    try:
        import httpx
        from database import get_session, init_db
    except Exception as exc:
        logger.exception("tie_forward_import_failed")
        return {"ok": False, "error": str(exc)}

    settings = load_settings()
    init_db(settings)
    messages_payload: list[dict[str, Any]] = []

    with get_session(settings) as session:
        cursor = (
            session.messages.find({"text": {"$exists": True, "$ne": ""}})
            .sort("scraped_at", -1)
            .limit(max(1, min(int(limit), 1000)))
        )
        chats = {c.id: c for c in session.list_chats()}
        for doc in cursor:
            text = (doc.get("text") or "").strip()
            if not text:
                continue
            chat_id = doc.get("chat_id")
            chat = chats.get(chat_id) if chat_id is not None else None
            channel = None
            if chat is not None:
                channel = chat.username or chat.title or str(chat.id)
            mid = doc.get("message_id")
            chat_part = doc.get("chat_id")
            message_id = f"{chat_part}:{mid}" if chat_part is not None and mid is not None else str(mid or uuid.uuid4())
            ts = doc.get("timestamp")
            if hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            messages_payload.append(
                {
                    "message_id": message_id,
                    "text": text,
                    "channel": channel,
                    "timestamp": ts,
                    "source": "telegram",
                }
            )

    if not messages_payload:
        return {"ok": True, "forwarded": 0, "detail": "no_messages"}

    batch_id = f"console-scrape-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    url = f"{_tie_base_url()}/api/v1/batches"
    body = {
        "batch_id": batch_id,
        "messages": messages_payload,
        "scrape_completed": True,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=_tie_auth_headers(), json=body)
        if resp.status_code >= 400:
            logger.error("tie_forward_failed status=%s body=%s", resp.status_code, resp.text[:300])
            return {
                "ok": False,
                "status_code": resp.status_code,
                "error": resp.text[:300],
                "batch_id": batch_id,
            }
        logger.info(
            "tie_forward_ok batch_id=%s messages=%s status=%s",
            batch_id,
            len(messages_payload),
            resp.status_code,
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "forwarded": len(messages_payload),
            "status_code": resp.status_code,
            "response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None,
        }
    except Exception as exc:
        logger.exception("tie_forward_network_error")
        return {"ok": False, "error": str(exc), "batch_id": batch_id}
