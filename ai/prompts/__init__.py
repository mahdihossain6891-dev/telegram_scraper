"""Versioned Markdown prompt management.

Public API::

    from ai.prompts import PromptLoader, KNOWN_PROMPT_IDS

    loader = PromptLoader()
    prompt = loader.render(
        "investigation_summary",
        subject_label="@alice",
        subject_id="123",
        time_range="2026-07-01 .. 2026-07-18",
        evidence_block="...",
        risk_indicators="...",
    )
"""

from __future__ import annotations

from .errors import (
    PromptError,
    PromptNotFoundError,
    PromptParseError,
    PromptRenderError,
)
from .loader import KNOWN_PROMPT_IDS, PromptLoader, default_prompts_root, extract_placeholders
from .models import PromptTemplate, RenderedPrompt

__all__ = [
    "KNOWN_PROMPT_IDS",
    "PromptError",
    "PromptLoader",
    "PromptNotFoundError",
    "PromptParseError",
    "PromptRenderError",
    "PromptTemplate",
    "RenderedPrompt",
    "default_prompts_root",
    "extract_placeholders",
]
