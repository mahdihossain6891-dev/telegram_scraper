"""TIE → Threat Console intelligence ingest.

Receives processed reports from the Threat Intelligence Engine via:
  POST /api/intelligence/reports

Auth: Authorization: Bearer {TIE_INGEST_API_KEY}
(also accepts THREAT_CONSOLE_API_KEY as alias)

Stores reports in Mongo collection ``tie_intelligence_reports`` (idempotent on message_id).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from database import get_db, init_db
from utils import get_logger

logger = get_logger("tie_ingest")

router = APIRouter(tags=["tie-ingest"])


class ConsoleRiskPayload(BaseModel):
    score: int = 0
    level: str = "Unknown"
    reasons: list[str] = Field(default_factory=list)


class ConsoleIntelligencePayload(BaseModel):
    """Matches TIE ``ConsoleIntelligencePayload`` (app/integration/models.py)."""

    message_id: str = Field(..., min_length=1)
    original_text: str = ""
    translated_text: str = ""
    language: str = "unknown"
    indicators: dict[str, Any] = Field(default_factory=dict)
    classification: dict[str, Any] = Field(default_factory=dict)
    risk: ConsoleRiskPayload
    channel: Optional[str] = None
    source: Optional[str] = None


def _ingest_api_key() -> str:
    return (
        os.getenv("TIE_INGEST_API_KEY", "").strip()
        or os.getenv("THREAT_CONSOLE_API_KEY", "").strip()
        or "dev-tie-console-shared-key"
    )


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _require_tie_auth(
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> None:
    expected = _ingest_api_key()
    token = _extract_bearer(authorization) or (x_api_key or "").strip()
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing TIE ingest credentials",
        )


def _collection():
    init_db()
    return get_db()["tie_intelligence_reports"]


def upsert_intelligence_report(payload: ConsoleIntelligencePayload) -> dict[str, Any]:
    col = _collection()
    now = datetime.now(timezone.utc)
    doc = {
        "message_id": payload.message_id,
        "original_text": payload.original_text,
        "translated_text": payload.translated_text,
        "language": payload.language,
        "indicators": payload.indicators,
        "classification": payload.classification,
        "risk": payload.risk.model_dump(),
        "channel": payload.channel,
        "source": payload.source or "tie",
        "received_at": now,
        "updated_at": now,
    }
    existing = col.find_one({"message_id": payload.message_id})
    if existing:
        col.update_one(
            {"message_id": payload.message_id},
            {
                "$set": {
                    **{k: v for k, v in doc.items() if k != "received_at"},
                    "updated_at": now,
                }
            },
        )
        return {"status": "updated", "message_id": payload.message_id}

    col.insert_one(doc)
    return {"status": "accepted", "message_id": payload.message_id}


@router.post("/api/intelligence/reports")
def receive_intelligence_report(
    payload: ConsoleIntelligencePayload,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Inbound endpoint for TIE ``ThreatConsoleClient.send_intelligence_report``."""
    _require_tie_auth(authorization, x_api_key)
    try:
        result = upsert_intelligence_report(payload)
    except Exception as exc:
        logger.exception("Failed to store TIE intelligence message_id=%s", payload.message_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store intelligence report: {exc}",
        ) from exc

    logger.info(
        "TIE intelligence %s message_id=%s risk=%s",
        result["status"],
        payload.message_id,
        payload.risk.level,
    )
    return result


@router.get("/api/intelligence/reports")
def list_intelligence_reports(
    limit: int = Query(default=50, ge=1, le=500),
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """List recent TIE-uploaded intelligence (ops / verification)."""
    _require_tie_auth(authorization, x_api_key)
    col = _collection()
    cursor = col.find({}, {"_id": 0}).sort("received_at", -1).limit(limit)
    items = list(cursor)
    return {"items": items, "count": len(items)}


@router.get("/api/intelligence/status")
def intelligence_ingest_status() -> dict[str, Any]:
    """Unauthenticated liveness for TIE health probes / ops."""
    try:
        col = _collection()
        count = col.count_documents({})
        return {
            "service": "Threat Console",
            "ingest": "ready",
            "endpoint": "/api/intelligence/reports",
            "reports_stored": count,
        }
    except Exception as exc:
        return {
            "service": "Threat Console",
            "ingest": "degraded",
            "error": str(exc),
        }


def build_tie_ingest_router() -> APIRouter:
    return router
