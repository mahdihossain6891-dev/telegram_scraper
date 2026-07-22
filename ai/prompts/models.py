"""Prompt template models (metadata only — body comes from Markdown files)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A loaded, versioned prompt template (unrendered)."""

    id: str
    version: str
    description: str
    body: str
    variables: tuple[str, ...] = ()
    path: str = ""

    @property
    def key(self) -> str:
        """Stable ``id@version`` identifier."""
        return f"{self.id}@{self.version}"


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """A prompt after variable substitution."""

    id: str
    version: str
    text: str
    variables_used: tuple[str, ...] = ()
    missing_optional: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"
