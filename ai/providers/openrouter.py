"""OpenRouter provider — OpenAI-compatible API via OpenRouter."""

from __future__ import annotations

from typing import Any

from ai.providers.models import DiscoveredModel, ModelCapabilities
from ai.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
)
from ai.providers.transport import get_json, join_url

_DEFAULT_BASE = "https://openrouter.ai/api/v1"


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class OpenRouterChatProvider(OpenAICompatibleChatProvider):
    """Chat provider for OpenRouter (https://openrouter.ai)."""

    name = "openrouter"

    def __init__(
        self,
        *,
        api_base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        default_max_tokens: int | None = None,
        http_referer: str = "",
        app_title: str = "Telegram Intelligence Platform",
    ) -> None:
        extra_headers: dict[str, str] = {}
        if http_referer:
            extra_headers["HTTP-Referer"] = http_referer
        if app_title:
            extra_headers["X-Title"] = app_title
        super().__init__(
            api_base_url=api_base_url,
            api_key=api_key,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            default_max_tokens=default_max_tokens,
            default_base_url=_DEFAULT_BASE,
            extra_headers=extra_headers or None,
            provider_name="openrouter",
        )

    def discover_models(self) -> list[DiscoveredModel]:
        """Query OpenRouter ``/models`` and normalize rich metadata."""
        data = get_json(
            join_url(self.api_base_url, "/models"),
            timeout_seconds=self.timeout_seconds,
            headers=self._headers(),
            provider=self.name,
            operation="list_models",
        )
        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        out: list[DiscoveredModel] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = row.get("id")
            if not isinstance(mid, str) or not mid.strip():
                continue
            name = row.get("name")
            display = name.strip() if isinstance(name, str) and name.strip() else mid.strip()
            arch = row.get("architecture") if isinstance(row.get("architecture"), dict) else {}
            modality = str(arch.get("modality") or "")
            input_modalities = arch.get("input_modalities")
            if isinstance(input_modalities, list):
                vision = "image" in [str(x).lower() for x in input_modalities]
            else:
                vision = "image" in modality.lower()
            supported = row.get("supported_parameters")
            supported_set = {
                str(x).lower() for x in supported if isinstance(x, str)
            } if isinstance(supported, list) else set()
            ctx = row.get("context_length")
            context_window = int(ctx) if isinstance(ctx, (int, float)) else None
            pricing_raw = row.get("pricing") if isinstance(row.get("pricing"), dict) else None
            pricing = None
            if pricing_raw:
                pricing = {
                    "prompt": _as_float(pricing_raw.get("prompt")),
                    "completion": _as_float(pricing_raw.get("completion")),
                    "request": _as_float(pricing_raw.get("request")),
                    "image": _as_float(pricing_raw.get("image")),
                }
            top = row.get("top_provider") if isinstance(row.get("top_provider"), dict) else {}
            max_completion = top.get("max_completion_tokens")
            max_tokens = (
                int(max_completion) if isinstance(max_completion, (int, float)) else None
            )
            reasoning = (
                "reasoning" in supported_set
                or "include_reasoning" in supported_set
                or bool(row.get("reasoning"))
            )
            tools = "tools" in supported_set or "tool_choice" in supported_set
            json_mode = "response_format" in supported_set or "structured_outputs" in supported_set
            out.append(
                DiscoveredModel(
                    model_id=mid.strip(),
                    display_name=display,
                    provider=self.name,
                    context_window=context_window,
                    max_tokens=max_tokens,
                    status="available",
                    pricing=pricing,
                    estimated_speed=None,
                    capabilities=ModelCapabilities(
                        supports_streaming=True,
                        supports_json_output=json_mode or True,
                        supports_vision=vision,
                        supports_reasoning=reasoning,
                        supports_tool_calling=tools,
                    ),
                    raw=dict(row),
                )
            )
        return out


class OpenRouterEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    """Embedding provider for OpenRouter OpenAI-compatible embeddings."""

    name = "openrouter"

    def __init__(
        self,
        *,
        api_base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        http_referer: str = "",
        app_title: str = "Telegram Intelligence Platform",
    ) -> None:
        extra_headers: dict[str, str] = {}
        if http_referer:
            extra_headers["HTTP-Referer"] = http_referer
        if app_title:
            extra_headers["X-Title"] = app_title
        super().__init__(
            api_base_url=api_base_url,
            api_key=api_key,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            default_base_url=_DEFAULT_BASE,
            extra_headers=extra_headers or None,
            provider_name="openrouter",
        )
