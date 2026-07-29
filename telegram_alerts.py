"""Send Telegram Bot API alerts for newly flagged OSINT activity."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import dotenv_values

from entity_extractor import collect_alert_addresses
from config import PROJECT_ROOT
from database import MongoSession, get_session, init_db
from utils import get_logger

logger = get_logger("telegram_alerts")

ALERT_STATE_ID = "telegram_alerts"


@dataclass(frozen=True)
class AlertConfig:
    """Runtime alert settings loaded from .env."""

    enabled: bool
    bot_token: str
    chat_id: str
    on_scrape: bool
    multi_category_only: bool
    min_keywords: int
    cooldown_seconds: int


@dataclass(frozen=True)
class AlertMessage:
    """A flagged message candidate for alerting."""

    chat_name: str
    message_id: int
    sender: str
    text: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...]
    timestamp: str | None = None
    addresses: tuple[str, ...] = ()
    alert_key: str | None = None


@dataclass(frozen=True)
class AlertSendResult:
    """Outcome of sending one Telegram alert."""

    ok: bool
    detail: str
    message_id: int | None = None


def _env_bool(values: dict[str, Any], name: str, default: bool = False) -> bool:
    raw = str(values.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def load_alert_config() -> AlertConfig:
    """Load alert settings from .env / environment."""
    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    token = str(values.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = str(values.get("TELEGRAM_ALERT_CHAT_ID", "")).strip()
    if chat_id.startswith("https://t.me/"):
        chat_id = chat_id.removeprefix("https://t.me/").strip("/")
    if chat_id and not chat_id.lstrip("-").isdigit():
        chat_id = chat_id if chat_id.startswith("@") else f"@{chat_id}"

    min_keywords = int(str(values.get("TELEGRAM_ALERT_MIN_KEYWORDS", "1")).strip() or "1")
    cooldown = int(str(values.get("TELEGRAM_ALERT_COOLDOWN_SECONDS", "60")).strip() or "60")

    return AlertConfig(
        enabled=_env_bool(values, "TELEGRAM_ALERTS_ENABLED", False),
        bot_token=token,
        chat_id=chat_id,
        on_scrape=_env_bool(values, "TELEGRAM_ALERT_ON_SCRAPE", True),
        multi_category_only=_env_bool(values, "TELEGRAM_ALERT_MULTI_CATEGORY_ONLY", False),
        min_keywords=max(1, min_keywords),
        cooldown_seconds=max(0, cooldown),
    )


def alert_status(config: AlertConfig | None = None) -> dict[str, Any]:
    """Return a dashboard-friendly alert status payload."""
    cfg = config or load_alert_config()
    state = _load_state()
    ready = bool(cfg.enabled and cfg.bot_token and cfg.chat_id)
    return {
        "enabled": cfg.enabled,
        "configured": bool(cfg.bot_token and cfg.chat_id),
        "ready": ready,
        "chat_id": cfg.chat_id or None,
        "on_scrape": cfg.on_scrape,
        "multi_category_only": cfg.multi_category_only,
        "min_keywords": cfg.min_keywords,
        "cooldown_seconds": cfg.cooldown_seconds,
        "bot_token_set": bool(cfg.bot_token),
        "last_alert_at": state.get("last_alert_at"),
        "last_alert_ok": state.get("last_alert_ok"),
        "last_alert_detail": state.get("last_alert_detail"),
        "alerts_sent": int(state.get("alerts_sent") or 0),
        "hint": _setup_hint(cfg),
    }


def _setup_hint(cfg: AlertConfig) -> str:
    if not cfg.bot_token:
        return "Set TELEGRAM_BOT_TOKEN in .env (create a bot with @BotFather)."
    if not cfg.chat_id:
        return (
            "Set TELEGRAM_ALERT_CHAT_ID to your Telegram user id or @channel. "
            "For DMs: open your bot and tap Start first."
        )
    if not cfg.enabled:
        return "Alerts are configured but TELEGRAM_ALERTS_ENABLED=0."
    return "Alerts are ready. New flagged scrapes can notify you on Telegram."


def _load_state() -> dict[str, Any]:
    try:
        init_db()
        with get_session() as session:
            doc = session.db["alert_state"].find_one({"_id": ALERT_STATE_ID}) or {}
            return dict(doc)
    except Exception:
        return {}


def _save_state(updates: dict[str, Any]) -> None:
    try:
        init_db()
        with get_session() as session:
            session.db["alert_state"].update_one(
                {"_id": ALERT_STATE_ID},
                {"$set": updates},
                upsert=True,
            )
    except Exception as exc:
        logger.warning("Could not persist alert state: %s", exc)


def _cooldown_active(cfg: AlertConfig, state: dict[str, Any]) -> bool:
    if cfg.cooldown_seconds <= 0:
        return False
    last = state.get("last_alert_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (datetime.now(timezone.utc) - last_dt.astimezone(timezone.utc)).total_seconds()
    return age < cfg.cooldown_seconds


def should_include_message(cfg: AlertConfig, categories: list[str] | tuple[str, ...], keywords: list[str] | tuple[str, ...], addresses: tuple[str, ...] = ()) -> bool:
    """Return True when a flagged message meets alert thresholds."""
    if addresses:
        return True
    if cfg.multi_category_only and len(set(categories)) < 2:
        return False
    if len(keywords) < cfg.min_keywords:
        return False
    return True


def format_alert_digest(
    items: list[AlertMessage],
    *,
    title: str = "OSINT alert",
) -> str:
    """Build a compact Telegram-friendly digest."""
    lines = [
        f"🔔 {title}",
        f"{len(items)} new flagged message(s)",
        "",
    ]
    for item in items[:8]:
        preview = (item.text or "").strip().replace("\n", " ")
        if len(preview) > 140:
            preview = preview[:137] + "..."
        cats = ", ".join(item.categories) or "flagged"
        kws = ", ".join(item.keywords[:6]) or "—"
        lines.append(f"• [{item.chat_name}] {item.sender}")
        lines.append(f"  {cats} · {kws}")
        if item.addresses:
            lines.append(f"  Address: {', '.join(item.addresses[:4])}")
        if preview:
            lines.append(f"  “{preview}”")
        lines.append("")
    if len(items) > 8:
        lines.append(f"…and {len(items) - 8} more")
    lines.append("Open the dashboard → Personnel / Messages for detail.")
    return "\n".join(lines).strip()


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> AlertSendResult:
    """Send one Bot API sendMessage call."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return AlertSendResult(ok=False, detail=detail or str(exc))
    except urllib.error.URLError as exc:
        return AlertSendResult(ok=False, detail=str(exc))

    if not body.get("ok"):
        return AlertSendResult(ok=False, detail=str(body))
    result = body.get("result") or {}
    return AlertSendResult(ok=True, detail="sent", message_id=result.get("message_id"))


def send_alert_digest(
    items: list[AlertMessage],
    *,
    title: str = "OSINT alert",
    force: bool = False,
    config: AlertConfig | None = None,
) -> AlertSendResult:
    """Send a digest alert if enabled and not in cooldown."""
    cfg = config or load_alert_config()
    if not items:
        return AlertSendResult(ok=False, detail="No items to alert")
    if not force and not cfg.enabled:
        return AlertSendResult(ok=False, detail="Alerts disabled")
    if not cfg.bot_token or not cfg.chat_id:
        return AlertSendResult(ok=False, detail="Bot token or alert chat id missing")

    state = _load_state()
    if not force and _cooldown_active(cfg, state):
        return AlertSendResult(ok=False, detail="Cooldown cooldown active")

    text = format_alert_digest(items, title=title)
    result = send_telegram_message(cfg.bot_token, cfg.chat_id, text)
    now = datetime.now(timezone.utc).isoformat()
    _save_state(
        {
            "last_alert_at": now,
            "last_alert_ok": result.ok,
            "last_alert_detail": result.detail[:500],
            "alerts_sent": int(state.get("alerts_sent") or 0) + (1 if result.ok else 0),
            "updated_at": now,
        }
    )
    if result.ok:
        logger.info("Sent Telegram alert digest (%s items) to %s", len(items), cfg.chat_id)
    else:
        logger.warning("Telegram alert failed: %s", result.detail)
    return result


def send_test_alert(config: AlertConfig | None = None) -> AlertSendResult:
    """Send a one-off test message to verify alert delivery."""
    cfg = config or load_alert_config()
    sample = [
        AlertMessage(
            chat_name="Alert test",
            message_id=0,
            sender="dashboard",
            text="This is a test alert from Telegram Scraper. If you received this, alerts work.",
            categories=("test",),
            keywords=("test",),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    ]
    return send_alert_digest(
        sample,
        title="OSINT alert test",
        force=True,
        config=cfg,
    )


def _alerted_keys(state: dict[str, Any]) -> set[str]:
    raw = state.get("alerted_keys") or []
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if item}


def _remember_alerted_keys(state: dict[str, Any], keys: list[str]) -> None:
    merged = list(_alerted_keys(state))
    for key in keys:
        if key and key not in merged:
            merged.append(key)
    if len(merged) > 500:
        merged = merged[-500:]
    _save_state({"alerted_keys": merged})


def alert_message_key(
    *,
    chat_name: str,
    message_id: int,
    explicit_key: str | None = None,
) -> str:
    if explicit_key:
        return explicit_key
    return f"{chat_name}:{message_id}"


def send_address_alerts(
    items: list[AlertMessage],
    *,
    config: AlertConfig | None = None,
) -> AlertSendResult:
    """Send alerts for messages with detected addresses, skipping duplicates."""
    cfg = config or load_alert_config()
    if not cfg.enabled:
        return AlertSendResult(ok=False, detail="Alerts disabled")
    if not cfg.bot_token or not cfg.chat_id:
        return AlertSendResult(ok=False, detail="Bot token or alert chat id missing")

    state = _load_state()
    already = _alerted_keys(state)
    pending: list[AlertMessage] = []
    pending_keys: list[str] = []
    for item in items:
        if not item.addresses:
            continue
        key = alert_message_key(
            chat_name=item.chat_name,
            message_id=item.message_id,
            explicit_key=item.alert_key,
        )
        if key in already:
            continue
        pending.append(item)
        pending_keys.append(key)

    if not pending:
        return AlertSendResult(ok=False, detail="No new address alerts to send")
    if _cooldown_active(cfg, state):
        return AlertSendResult(ok=False, detail="Cooldown active")

    result = send_alert_digest(
        pending,
        title="OSINT alert · address detected",
        force=True,
        config=cfg,
    )
    if result.ok:
        _track_sent_alert_items(pending)
    return result


def _track_sent_alert_items(items: list[AlertMessage]) -> None:
    state = _load_state()
    keys = [
        alert_message_key(
            chat_name=item.chat_name,
            message_id=item.message_id,
            explicit_key=item.alert_key,
        )
        for item in items
    ]
    _remember_alerted_keys(state, keys)


def maybe_alert_after_scrape(
    items: list[AlertMessage],
    *,
    chat_name: str,
) -> AlertSendResult | None:
    """Filter scrape hits and send a digest when alerts are enabled."""
    cfg = load_alert_config()
    if not cfg.enabled or not cfg.on_scrape:
        return None
    filtered = [
        item
        for item in items
        if should_include_message(cfg, item.categories, item.keywords, item.addresses)
    ]
    if not filtered:
        return None
    title = "OSINT alert · address detected" if any(item.addresses for item in filtered) else f"OSINT alert · {chat_name}"
    result = send_alert_digest(
        filtered,
        title=title,
        config=cfg,
    )
    if result.ok:
        _track_sent_alert_items(filtered)
    return result
