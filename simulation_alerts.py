"""Simulation-mode alert logging — same UX as live without Telegram delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from telegram_alerts import AlertMessage, AlertSendResult

_STATE: dict[str, Any] = {
    "alerts_sent": 0,
    "last_alert_at": None,
    "last_alert_ok": None,
    "last_alert_detail": None,
    "keys": set(),
}


def reset_simulation_alerts() -> None:
    """Clear in-memory simulation alert state (e.g. when ending simulation)."""
    _STATE["alerts_sent"] = 0
    _STATE["last_alert_at"] = None
    _STATE["last_alert_ok"] = None
    _STATE["last_alert_detail"] = None
    _STATE["keys"] = set()


def simulation_alert_status() -> dict[str, Any]:
    """Dashboard-friendly alert status while simulation mode is active."""
    return {
        "enabled": True,
        "configured": True,
        "ready": True,
        "simulation_mode": True,
        "chat_id": "simulation-log",
        "on_scrape": True,
        "multi_category_only": False,
        "min_keywords": 1,
        "cooldown_seconds": 0,
        "bot_token_set": False,
        "last_alert_at": _STATE.get("last_alert_at"),
        "last_alert_ok": _STATE.get("last_alert_ok"),
        "last_alert_detail": _STATE.get("last_alert_detail"),
        "alerts_sent": int(_STATE.get("alerts_sent") or 0),
        "hint": (
            "Simulation mode: address alerts are logged locally and are not sent to Telegram."
        ),
    }


def send_simulation_test_alert() -> AlertSendResult:
    """Record a simulation test alert."""
    now = datetime.now(timezone.utc).isoformat()
    _STATE["alerts_sent"] = int(_STATE.get("alerts_sent") or 0) + 1
    _STATE["last_alert_at"] = now
    _STATE["last_alert_ok"] = True
    _STATE["last_alert_detail"] = "Simulation test alert logged (not sent to Telegram)."
    return AlertSendResult(ok=True, detail=_STATE["last_alert_detail"])


def send_simulation_address_alerts(items: list[AlertMessage]) -> AlertSendResult:
    """Log address alerts for flagged simulation messages."""
    if not items:
        return AlertSendResult(ok=False, detail="No address alerts to send")

    keys: set[str] = _STATE.setdefault("keys", set())
    fresh = [
        item
        for item in items
        if item.addresses
        and (item.alert_key or f"{item.chat_name}:{item.message_id}") not in keys
    ]
    if not fresh:
        return AlertSendResult(ok=False, detail="No new address alerts to send")

    for item in fresh:
        key = item.alert_key or f"{item.chat_name}:{item.message_id}"
        keys.add(key)

    now = datetime.now(timezone.utc).isoformat()
    _STATE["alerts_sent"] = int(_STATE.get("alerts_sent") or 0) + len(fresh)
    _STATE["last_alert_at"] = now
    _STATE["last_alert_ok"] = True
    _STATE["last_alert_detail"] = (
        f"Simulation: logged {len(fresh)} address alert(s) (not sent to Telegram)."
    )
    return AlertSendResult(ok=True, detail=_STATE["last_alert_detail"])
