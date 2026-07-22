"""Isolated FastAPI router for AI services under ``/api/ai``.

Routes communicate only with ``AIServiceFacade``. They never accept or return
database sessions. Mount with ``app.include_router(build_ai_router())``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ai.api.facade import AIServiceFacade
from ai.api.schemas import (
    CacheClearBody,
    ChatBody,
    InvestigateBody,
    ProviderTestBody,
    QueryBody,
    ReportBody,
    SessionDismissBody,
    SummaryBody,
)
from ai.providers.errors import ProviderConfigurationError, ProviderError

logger = logging.getLogger("ai.api.routes")


def build_ai_router(facade: AIServiceFacade | None = None) -> APIRouter:
    """Return an ``APIRouter`` mounted at ``/api/ai``."""
    services = facade or AIServiceFacade()
    router = APIRouter(prefix="/api/ai", tags=["ai"])

    @router.get("/health")
    def ai_health() -> JSONResponse:
        return JSONResponse(services.health())

    @router.get("/providers")
    def ai_providers(refresh: bool = False) -> JSONResponse:
        """List available chat providers with health (additive discovery API)."""
        return JSONResponse(_call(services.list_providers, refresh=refresh))

    @router.get("/planner")
    def ai_planner(
        question: str | None = None,
        subject_id: str | None = None,
    ) -> JSONResponse:
        """Investigation Planner catalog + optional plan preview (additive)."""
        subject = {"subject_id": subject_id} if subject_id else None
        return JSONResponse(
            _call(services.planner_info, question=question, subject=subject)
        )

    @router.get("/tools")
    def ai_tools() -> JSONResponse:
        """Registered investigation tools and capabilities (additive)."""
        return JSONResponse(_call(services.list_tools_catalog))

    @router.get("/models")
    def ai_models(
        provider: str | None = None,
        refresh: bool = False,
    ) -> JSONResponse:
        """List discovered models for the selected (or queried) provider."""
        return JSONResponse(
            _call(services.list_models, provider=provider, refresh=refresh)
        )

    @router.get("/provider/health")
    def ai_provider_health(
        provider: str | None = None,
        refresh: bool = False,
    ) -> JSONResponse:
        """Provider health, latency, and capability snapshot."""
        return JSONResponse(
            _call(services.provider_health, provider=provider, refresh=refresh)
        )

    @router.post("/query")
    def ai_query(body: QueryBody) -> JSONResponse:
        return JSONResponse(_call(services.query, body.question, top_k=body.top_k, filters=body.filters))

    @router.post("/summary")
    def ai_summary(body: SummaryBody) -> JSONResponse:
        return JSONResponse(
            _call(
                services.summary,
                subject_id=body.subject_id,
                subject_type=body.subject_type,
                subject_label=body.subject_label,
                filters=body.filters,
                analyst_notes=body.analyst_notes,
            )
        )

    @router.post("/report")
    def ai_report(body: ReportBody) -> JSONResponse:
        return JSONResponse(
            _call(
                services.report,
                report_type=body.report_type,
                subject_id=body.subject_id,
                subject_type=body.subject_type,
                subject_label=body.subject_label,
                filters=body.filters,
                analyst_notes=body.analyst_notes,
                title=body.title,
                persist=body.persist,
            )
        )

    @router.post("/investigate")
    def ai_investigate(body: InvestigateBody) -> JSONResponse:
        return JSONResponse(
            _call(
                services.investigate,
                body.question,
                session_id=body.session_id,
                subject=body.subject or None,
                filters=body.filters,
                deselected_tools=body.deselected_tools or None,
                provider=body.provider,
                model=body.model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        )

    @router.post("/chat")
    def ai_chat(body: ChatBody) -> JSONResponse:
        return JSONResponse(
            _call(
                services.chat,
                body.message,
                session_id=body.session_id,
                subject=body.subject or None,
                filters=body.filters,
                provider=body.provider,
                model=body.model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            )
        )

    @router.post("/session/dismiss")
    def ai_session_dismiss(body: SessionDismissBody) -> JSONResponse:
        """Soft-dismiss an investigation session in ``ai_sessions`` only."""
        return JSONResponse(_call(services.dismiss_session, body.session_id))

    @router.post("/cache/clear")
    def ai_cache_clear(body: CacheClearBody | None = None) -> JSONResponse:
        """Clear model discovery cache — never touches intel data."""
        payload = body or CacheClearBody()
        return JSONResponse(_call(services.clear_model_cache, provider=payload.provider))

    @router.post("/provider/test")
    def ai_provider_test(body: ProviderTestBody | None = None) -> JSONResponse:
        """Live provider connectivity test for the Control Center."""
        payload = body or ProviderTestBody()
        return JSONResponse(_call(services.test_provider, provider=payload.provider))

    @router.post("/prompts/reload")
    def ai_prompts_reload() -> JSONResponse:
        """Reload prompt templates from disk into a fresh loader cache."""
        return JSONResponse(_call(services.reload_prompts))

    return router


def _call(func: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Invoke a facade method and map provider errors to HTTP errors."""
    try:
        return func(*args, **kwargs)
    except ProviderConfigurationError as exc:
        logger.info("ai_api_not_ready", extra={"ai_detail": str(exc)})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        logger.warning("ai_api_provider_error", extra={"ai_detail": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("ai_api_internal_error")
        raise HTTPException(
            status_code=500,
            detail="AI service error. See server logs for details.",
        ) from exc
