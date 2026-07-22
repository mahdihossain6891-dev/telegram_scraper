"""JSON-mode helper over ``ChatModelProvider`` (parse model JSON safely)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Sequence

from ai.providers.base import ChatMessage, ChatModelProvider
from ai.providers.errors import ProviderConfigurationError, ProviderResponseError

logger = logging.getLogger("ai.llm.json_mode")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class JSONModeClient:
    """Request a completion and parse the response as a JSON object."""

    def __init__(
        self,
        provider: ChatModelProvider,
        *,
        default_model: str = "",
        default_max_tokens: int | None = 1024,
        default_temperature: float | None = 0.0,
    ) -> None:
        self.provider = provider
        self.default_model = default_model.strip()
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

    def complete_json(
        self,
        messages: Sequence[ChatMessage],
        *,
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model response."""
        if not messages:
            raise ProviderConfigurationError(
                "messages must not be empty",
                provider=getattr(self.provider, "name", None),
                operation="json",
            )

        call_extra = dict(extra or {})
        if schema is not None:
            # Providers that understand Ollama/OpenAI json schema can use this.
            call_extra.setdefault("format", "json")

        completion = self.provider.complete(
            messages,
            model=(model or self.default_model or None),
            max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
            temperature=self.default_temperature,
            extra=call_extra or None,
        )
        return parse_json_object(completion.content)


def parse_json_object(content: str) -> dict[str, Any]:
    """Extract a JSON object from model text (strips optional fences)."""
    text = (content or "").strip()
    if not text:
        raise ProviderResponseError("Model returned empty JSON content")

    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Best-effort: first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ProviderResponseError(
                "Model response was not valid JSON",
                details={"body": text[:500]},
            )
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(
                "Model response was not valid JSON",
                details={"body": text[:500]},
            ) from exc

    if not isinstance(parsed, dict):
        raise ProviderResponseError(
            "JSON root must be an object",
            details={"type": type(parsed).__name__},
        )
    return parsed
