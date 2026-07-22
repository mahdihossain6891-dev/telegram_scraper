"""Normalized model metadata — provider-agnostic.

The UI and Model Registry consume these structures only. Provider-specific
payloads are normalized inside discovery adapters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelCapabilities:
    """Capability flags shared across all providers."""

    supports_streaming: bool = True
    supports_json_output: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_tool_calling: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiscoveredModel:
    """Single discovered model entry for Sebastian's model picker."""

    model_id: str
    display_name: str
    provider: str
    context_window: int | None = None
    max_tokens: int | None = None
    status: str = "available"
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    family: str | None = None
    size_bytes: int | None = None
    quantization: str | None = None
    modified_at: str | None = None
    pricing: dict[str, Any] | None = None
    estimated_speed: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "context_window": self.context_window,
            "max_tokens": self.max_tokens,
            "status": self.status,
            "capabilities": self.capabilities.to_dict(),
            "family": self.family,
            "size_bytes": self.size_bytes,
            "quantization": self.quantization,
            "modified_at": self.modified_at,
            "pricing": self.pricing,
            "estimated_speed": self.estimated_speed,
        }


@dataclass(slots=True)
class ProviderDescriptor:
    """Registered provider entry for the providers catalog API."""

    id: str
    label: str
    kind: str  # local | remote | openai_compatible
    requires_api_key: bool = False
    default_base_url: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Catalog of known provider ids — labels only, never model names.
KNOWN_PROVIDERS: tuple[ProviderDescriptor, ...] = (
    ProviderDescriptor(
        id="ollama",
        label="Ollama",
        kind="local",
        requires_api_key=False,
        default_base_url="http://127.0.0.1:11434",
        description="Local Ollama runtime",
    ),
    ProviderDescriptor(
        id="openrouter",
        label="OpenRouter",
        kind="remote",
        requires_api_key=True,
        default_base_url="https://openrouter.ai/api/v1",
        description="OpenRouter multi-model gateway",
    ),
    ProviderDescriptor(
        id="lmstudio",
        label="LM Studio",
        kind="local",
        requires_api_key=False,
        default_base_url="http://127.0.0.1:1234/v1",
        description="LM Studio OpenAI-compatible local server",
    ),
    ProviderDescriptor(
        id="openai_compatible",
        label="OpenAI Compatible",
        kind="openai_compatible",
        requires_api_key=False,
        default_base_url="",
        description="Generic OpenAI-compatible HTTP endpoint",
    ),
    ProviderDescriptor(
        id="local",
        label="Local (Ollama)",
        kind="local",
        requires_api_key=False,
        default_base_url="http://127.0.0.1:11434",
        description="Alias for Ollama",
    ),
)
