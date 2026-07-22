"""Pydantic request bodies for ``/api/ai`` (no database types)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryBody(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)


class SummaryBody(BaseModel):
    subject_id: str = Field(..., min_length=1)
    subject_type: str = "user"
    subject_label: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    analyst_notes: str = ""


class ReportBody(BaseModel):
    report_type: str = Field(
        ...,
        description=(
            "user_intelligence | investigation | case_summary | behavioral_analysis"
        ),
    )
    subject_id: str = Field(..., min_length=1)
    subject_type: str = "user"
    subject_label: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    analyst_notes: str = ""
    title: str | None = None
    persist: bool = True


class InvestigateBody(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    subject: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    """Optional tools the analyst deselected from the plan preview (Phase 5)."""
    deselected_tools: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    subject: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)


class SessionDismissBody(BaseModel):
    """Soft-dismiss an ``ai_sessions`` investigation session (no hard delete)."""

    session_id: str = Field(..., min_length=1)


class CacheClearBody(BaseModel):
    """Clear model-discovery cache (optional provider scope)."""

    provider: str | None = None


class ProviderTestBody(BaseModel):
    """Probe a chat provider without mutating investigation state."""

    provider: str | None = None


class PromptsReloadBody(BaseModel):
    """Reload prompt templates from disk."""

    pass
