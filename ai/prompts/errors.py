"""Prompt management errors."""

from __future__ import annotations


class PromptError(Exception):
    """Base error for prompt loading and rendering."""


class PromptNotFoundError(PromptError):
    """Requested prompt id / version does not exist on disk."""


class PromptParseError(PromptError):
    """Prompt Markdown / front matter could not be parsed."""


class PromptRenderError(PromptError):
    """Variable substitution failed (missing or unexpected variables)."""
