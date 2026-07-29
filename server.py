"""FastAPI live data API for the Next.js Telegram OSINT dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from config import ensure_directories, load_settings
from database import database_available, get_session, init_db
from data_providers import get_data_provider
from behavioral_analytics import rebuild_behavioral_analytics
from personnel import rebuild_user_activity
from scrape_jobs import get_scrape_job_store, start_scrape_job_in_background
from env_settings import env_settings_payload, update_env_settings
from telegram_alerts import AlertMessage, alert_status, send_address_alerts, send_test_alert

app = FastAPI(title="Telegram Scraper API", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Isolated module routers — must load with the main app (not a stale uvicorn worker).
from ai.api import build_ai_router  # noqa: E402
from tie_ingest import build_tie_ingest_router  # noqa: E402

app.include_router(build_ai_router())
app.include_router(build_tie_ingest_router())

import logging as _log  # noqa: E402

_log.getLogger("uvicorn.error").info(
    "Loaded /api/ai, /api/intelligence routers"
)


class TieEngineBody(BaseModel):
    enabled: bool = Field(..., description="When true, scrapes forward to TIE; when false, Console built-in analyser only")


@app.get("/api/tie-engine")
def api_tie_engine_get() -> JSONResponse:
    """TIE on/off mode for Threat Intelligence page."""
    from tie_engine_mode import get_tie_engine_mode

    return JSONResponse(get_tie_engine_mode())


@app.put("/api/tie-engine")
def api_tie_engine_set(body: TieEngineBody) -> JSONResponse:
    """Enable or disable TIE processing after scrapes."""
    from tie_engine_mode import set_tie_engine_mode

    return JSONResponse(set_tie_engine_mode(body.enabled))


@app.get("/api/investigations")
def api_investigations() -> JSONResponse:
    """Investigation data from live MongoDB."""
    provider = get_data_provider()
    return JSONResponse(provider.get_investigations())


def _parse_optional_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "scrape_router": "sim-limits-v2"}


@app.get("/api/data")
def api_data() -> JSONResponse:
    provider = get_data_provider()
    source, payload = provider.source_label, provider.get_export_payload()
    return JSONResponse({"source": source, "payload": payload, "mode": "live"})


@app.get("/api/personnel")
def api_personnel(
    chat_id: int | None = None,
    suspicious_only: bool = False,
    keyword: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = Query(
        "suspicious_count",
        pattern="^(suspicious_count|message_count|last_seen|keyword_total|display_name)$",
    ),
) -> JSONResponse:
    provider = get_data_provider()
    rows = provider.list_personnel(
        chat_id=chat_id,
        suspicious_only=suspicious_only,
        keyword=keyword,
        query=q,
        date_from=_parse_optional_date(date_from),
        date_to=_parse_optional_date(date_to),
        sort_by=sort_by,
    )
    return JSONResponse(
        {
            "source": provider.source_label,
            "mode": provider.mode,
            "personnel": rows,
            "count": len(rows),
        }
    )


@app.get("/api/personnel/{user_id}")
def api_personnel_detail(user_id: int) -> JSONResponse:
    provider = get_data_provider()
    detail = provider.get_personnel_detail(user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="User not found")
    return JSONResponse(
        {"source": provider.source_label, "mode": provider.mode, "detail": detail}
    )


@app.post("/api/personnel/rebuild")
def api_personnel_rebuild() -> JSONResponse:
    provider = get_data_provider()
    settings = ensure_directories(load_settings())
    if not database_available(settings):
        raise HTTPException(status_code=503, detail="MongoDB unavailable")
    init_db(settings)
    with get_session(settings) as session:
        count = rebuild_user_activity(session)
    return JSONResponse({"rebuilt_from_messages": count})


# ---------------------------------------------------------------------------
# Behavioral Analytics (isolated module — does not alter existing features)
# ---------------------------------------------------------------------------


def _behavioral_session():
    settings = ensure_directories(load_settings())
    if not database_available(settings):
        raise HTTPException(status_code=503, detail="MongoDB unavailable")
    init_db(settings)
    return settings


@app.get("/api/behavioral/overview")
def api_behavioral_overview() -> JSONResponse:
    provider = get_data_provider()
    overview = provider.behavioral_overview()
    return JSONResponse(
        {"source": provider.source_label, "mode": provider.mode, "overview": overview}
    )


@app.get("/api/behavioral/profiles")
def api_behavioral_profiles(
    q: str | None = None,
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    status: str | None = None,
    chat_id: int | None = None,
    language: str | None = None,
    behavior_type: str | None = None,
    sort_by: str = Query(
        "behavior_score",
        pattern="^(behavior_score|display_name|last_seen|average_messages_per_day|forward_ratio)$",
    ),
    limit: int = Query(200, ge=1, le=1000),
) -> JSONResponse:
    provider = get_data_provider()
    rows = provider.list_behavioral_profiles(
        q=q,
        min_score=min_score,
        max_score=max_score,
        status=status,
        chat_id=chat_id,
        language=language,
        behavior_type=behavior_type,
        sort_by=sort_by,
        limit=limit,
    )
    return JSONResponse(
        {
            "source": provider.source_label,
            "mode": provider.mode,
            "profiles": rows,
            "count": len(rows),
        }
    )


@app.get("/api/behavioral/profiles/{user_id}")
def api_behavioral_profile(user_id: int) -> JSONResponse:
    provider = get_data_provider()
    profile = provider.get_behavioral_profile(user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Behavioral profile not found.",
        )
    return JSONResponse(
        {"source": provider.source_label, "mode": provider.mode, "profile": profile}
    )


@app.post("/api/behavioral/rebuild")
def api_behavioral_rebuild() -> JSONResponse:
    provider = get_data_provider()
    settings = _behavioral_session()
    with get_session(settings) as session:
        stats = rebuild_behavioral_analytics(session)
    return JSONResponse({"source": "mongodb", "stats": stats})


@app.get("/api/alerts/status")
def api_alerts_status() -> JSONResponse:
    return JSONResponse(alert_status())


@app.post("/api/alerts/test")
def api_alerts_test() -> JSONResponse:
    result = send_test_alert()
    status = alert_status()
    if not result.ok:
        raise HTTPException(
            status_code=400,
            detail={
                "message": result.detail,
                "status": status,
            },
        )
    return JSONResponse({"ok": True, "detail": result.detail, "status": status})


class EnvSettingsBody(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


@app.get("/api/settings/env")
def api_settings_env_get() -> JSONResponse:
    """Return managed .env keys (secrets masked)."""
    return JSONResponse(env_settings_payload())


@app.put("/api/settings/env")
def api_settings_env_put(body: EnvSettingsBody) -> JSONResponse:
    """Update managed .env keys from the dashboard settings UI."""
    try:
        snapshot = update_env_settings(body.values)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {exc}") from exc
    try:
        from ai.config import reload_ai_settings

        reload_ai_settings()
    except Exception:
        pass
    return JSONResponse(
        {
            "ok": True,
            "values": snapshot.values,
            "configured": snapshot.configured,
            "env_path": snapshot.env_path,
            "env_exists": snapshot.env_exists,
            "hint": "Restart dashboard.bat if Telegram scrape auth still uses old credentials.",
        }
    )


class AddressAlertItem(BaseModel):
    chat_name: str
    message_id: int
    sender: str = "unknown"
    text: str = ""
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    alert_key: str | None = None
    timestamp: str | None = None


class AddressAlertBody(BaseModel):
    items: list[AddressAlertItem] = Field(default_factory=list)


@app.post("/api/alerts/auto")
def api_alerts_auto(body: AddressAlertBody) -> JSONResponse:
    """Send Telegram alerts for flagged messages that include detected addresses."""
    provider = get_data_provider()
    items = [
        AlertMessage(
            chat_name=item.chat_name,
            message_id=item.message_id,
            sender=item.sender,
            text=item.text,
            categories=tuple(item.categories),
            keywords=tuple(item.keywords),
            addresses=tuple(item.addresses),
            alert_key=item.alert_key,
            timestamp=item.timestamp,
        )
        for item in body.items
        if item.addresses
    ]
    if provider.mode != "live":
        raise HTTPException(status_code=409, detail="Alerts require live mode.")
    result = send_address_alerts(items)
    status = alert_status()
    if not result.ok and result.detail not in {
        "No new address alerts to send",
        "Cooldown active",
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "message": result.detail,
                "status": status,
            },
        )
    return JSONResponse(
        {
            "ok": result.ok,
            "detail": result.detail,
            "sent": result.ok,
            "status": status,
        }
    )


class ScrapeStartBody(BaseModel):
    limit: int | None = Field(
        default=None,
        description="Messages per monitored channel (100/500/1000)",
    )


@app.get("/api/scrape/status")
def api_scrape_status() -> JSONResponse:
    """Current or last scrape job snapshot for dashboard polling."""
    return JSONResponse(get_scrape_job_store().to_dict())


@app.post("/api/scrape/start")
def api_scrape_start(body: ScrapeStartBody | None = None) -> JSONResponse:
    """Start a background live Telegram scrape."""
    settings = ensure_directories(load_settings())
    if not database_available(settings):
        raise HTTPException(status_code=503, detail="MongoDB unavailable")

    payload = body or ScrapeStartBody()
    if payload.limit is not None and payload.limit not in (100, 500, 1000):
        raise HTTPException(
            status_code=400,
            detail="limit must be one of: 100, 500, 1000",
        )

    started = start_scrape_job_in_background(settings, limit=payload.limit)
    if not started:
        raise HTTPException(status_code=409, detail="Scrape job already running")
    return JSONResponse({"ok": True, "status": get_scrape_job_store().to_dict()})


@app.get("/")
def index() -> RedirectResponse:
    """Point browsers at the Next.js UI."""
    return RedirectResponse(url="http://127.0.0.1:3000")
