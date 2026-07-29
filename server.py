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
from data_providers import (
    end_simulation_mode,
    get_data_provider,
    get_mode_state,
    set_simulation_mode,
    start_simulation_mode,
)
from simulator.generation.scenarios import format_console_scenarios, parse_console_scenarios
from behavioral_analytics import rebuild_behavioral_analytics
from personnel import rebuild_user_activity
from scrape_jobs import get_scrape_job_store, start_scrape_job_in_background, start_simulation_scrape_in_background
from env_settings import env_settings_payload, update_env_settings
from telegram_alerts import AlertMessage, alert_status, send_address_alerts, send_test_alert
from simulation_alerts import (
    send_simulation_address_alerts,
    send_simulation_test_alert,
    simulation_alert_status,
)

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
from evaluation.api import build_evaluation_router  # noqa: E402
from tie_ingest import build_tie_ingest_router  # noqa: E402

app.include_router(build_ai_router())
app.include_router(build_evaluation_router())
app.include_router(build_tie_ingest_router())

import logging as _log  # noqa: E402

_log.getLogger("uvicorn.error").info(
    "Loaded /api/ai, /api/evaluation, /api/intelligence routers"
)


class ModeBody(BaseModel):
    mode: str = Field(..., description="live or simulation")
    scenario: str | None = None
    session_id: str | None = None
    session_name: str | None = None
    auto_start: bool = True


@app.get("/api/mode")
def api_mode() -> JSONResponse:
    state = get_mode_state()
    return JSONResponse(state.to_dict())


@app.put("/api/mode")
def api_mode_set(body: ModeBody) -> JSONResponse:
    normalized = (body.mode or "live").lower()
    if normalized == "live":
        state = end_simulation_mode()
    elif normalized == "simulation":
        scenario_raw = body.scenario
        if scenario_raw:
            scenario_raw = format_console_scenarios(parse_console_scenarios(scenario_raw))
        if body.session_id:
            state = set_simulation_mode(
                mode="simulation",
                scenario=scenario_raw or body.scenario,
                session_id=body.session_id,
                session_name=body.session_name,
            )
        else:
            state = start_simulation_mode(
                scenario=scenario_raw or body.scenario,
                session_name=body.session_name,
                auto_start=body.auto_start,
            )
    else:
        raise HTTPException(status_code=400, detail="mode must be 'live' or 'simulation'")
    return JSONResponse(state.to_dict())


@app.post("/api/mode/end")
def api_mode_end() -> JSONResponse:
    """Destroy simulation session and return console to live data."""
    state = end_simulation_mode()
    return JSONResponse(state.to_dict())


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
    """Investigation data from the active provider — live MongoDB or simulation."""
    provider = get_data_provider()
    state = get_mode_state()
    body = provider.get_investigations()
    body["simulation_state"] = state.to_dict()
    return JSONResponse(body)


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
    state = get_mode_state()
    source, payload = provider.source_label, provider.get_export_payload()
    return JSONResponse(
        {
            "source": source,
            "payload": payload,
            "mode": state.mode,
            "simulation_state": state.to_dict(),
        }
    )


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
    if provider.mode == "simulation":
        from database import get_session_for_database, get_simulation_database_name

        with get_session_for_database(get_simulation_database_name(), settings) as session:
            count = rebuild_user_activity(session)
        return JSONResponse(
            {"rebuilt_from_messages": count, "mode": "simulation", "source": provider.source_label}
        )
    if not provider.allows_live_operations():
        raise HTTPException(
            status_code=409,
            detail="Personnel rebuild is disabled in simulation mode.",
        )
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
    if provider.mode == "simulation":
        from database import get_session_for_database, get_simulation_database_name

        with get_session_for_database(get_simulation_database_name(), settings) as session:
            stats = rebuild_behavioral_analytics(session)
        return JSONResponse(
            {"source": provider.source_label, "mode": "simulation", "stats": stats}
        )
    if not provider.allows_live_operations():
        raise HTTPException(
            status_code=409,
            detail="Behavioral rebuild is disabled in simulation mode.",
        )
    with get_session(settings) as session:
        stats = rebuild_behavioral_analytics(session)
    return JSONResponse({"source": "mongodb", "stats": stats})


@app.get("/api/alerts/status")
def api_alerts_status() -> JSONResponse:
    provider = get_data_provider()
    if provider.mode == "simulation":
        return JSONResponse(simulation_alert_status())
    return JSONResponse(alert_status())


@app.post("/api/alerts/test")
def api_alerts_test() -> JSONResponse:
    provider = get_data_provider()
    if provider.mode == "simulation":
        result = send_simulation_test_alert()
        return JSONResponse(
            {
                "ok": True,
                "detail": result.detail,
                "status": simulation_alert_status(),
                "simulation": True,
            }
        )
    if not provider.allows_live_operations():
        raise HTTPException(
            status_code=409,
            detail="Live Telegram alerts are disabled in simulation mode.",
        )
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
    if provider.mode == "simulation":
        result = send_simulation_address_alerts(items)
        status = simulation_alert_status()
        if not result.ok and result.detail not in {
            "No new address alerts to send",
            "Cooldown active",
            "No address alerts to send",
        }:
            raise HTTPException(
                status_code=400,
                detail={"message": result.detail, "status": status},
            )
        return JSONResponse(
            {
                "ok": result.ok,
                "detail": result.detail,
                "sent": result.ok,
                "status": status,
                "simulation": True,
            }
        )
    if not provider.allows_live_operations():
        raise HTTPException(
            status_code=409,
            detail="Live Telegram alerts are disabled in simulation mode.",
        )
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
    model: str | None = Field(
        default=None,
        description="Optional AI chat model override for simulation dummy scrape",
    )
    scenario: str | None = Field(
        default=None,
        description="Simulation threat scenario (narcotics, firearms, human_trafficking)",
    )


@app.get("/api/scrape/status")
def api_scrape_status() -> JSONResponse:
    """Current or last scrape job snapshot for dashboard polling."""
    return JSONResponse(get_scrape_job_store().to_dict())


@app.post("/api/scrape/start")
def api_scrape_start(body: ScrapeStartBody | None = None) -> JSONResponse:
    """Start a background scrape — live Telegram or simulation AI dummy scrape."""
    settings = ensure_directories(load_settings())
    if not database_available(settings):
        raise HTTPException(status_code=503, detail="MongoDB unavailable")

    payload = body or ScrapeStartBody()
    mode_state = get_mode_state()
    sim_limits = {12, 16, 24, 32, 48, 64, 80}
    wants_simulation = (
        (mode_state.mode == "simulation" and mode_state.simulation_active)
        or bool((payload.scenario or "").strip())
        or (payload.limit is not None and int(payload.limit) in sim_limits)
    )

    if wants_simulation:
        if not (mode_state.mode == "simulation" and mode_state.simulation_active):
            start_simulation_mode(
                scenario=payload.scenario or mode_state.scenario or "narcotics",
                session_name=mode_state.session_name or "Console simulation",
                auto_start=False,
            )
            mode_state = get_mode_state()
        sim_limit = min(int(payload.limit or 24), 80)
        scenario = format_console_scenarios(
            parse_console_scenarios(payload.scenario or mode_state.scenario or "narcotics")
        )
        if scenario:
            from data_providers.state import update_mode_state

            update_mode_state(scenario=scenario)
        started = start_simulation_scrape_in_background(
            settings,
            scenario=scenario,
            limit=sim_limit,
            model=(payload.model or "").strip() or None,
            reset_database=True,
        )
        if not started:
            # Force-clear a stuck slot and retry once.
            store = get_scrape_job_store()
            if store.is_running():
                store.fail("Previous generate job interrupted — retrying.")
            started = start_simulation_scrape_in_background(
                settings,
                scenario=scenario,
                limit=sim_limit,
                model=(payload.model or "").strip() or None,
                reset_database=True,
            )
        if not started:
            raise HTTPException(status_code=409, detail="Scrape job already running")
        return JSONResponse(
            {
                "ok": True,
                "mode": "simulation",
                "status": get_scrape_job_store().to_dict(),
            }
        )

    provider = get_data_provider()
    if payload.limit is not None and payload.limit not in (100, 500, 1000):
        raise HTTPException(
            status_code=400,
            detail="limit must be one of: 100, 500, 1000",
        )

    if not provider.allows_live_operations():
        raise HTTPException(
            status_code=409,
            detail="Live Telegram scraping is disabled in simulation mode.",
        )

    started = start_scrape_job_in_background(settings, limit=payload.limit)
    if not started:
        raise HTTPException(status_code=409, detail="Scrape job already running")
    return JSONResponse({"ok": True, "status": get_scrape_job_store().to_dict()})


@app.get("/")
def index() -> RedirectResponse:
    """Point browsers at the Next.js UI."""
    return RedirectResponse(url="http://127.0.0.1:3000")
