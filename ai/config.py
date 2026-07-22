"""AI_* environment configuration only.

This module intentionally does **not** import or mutate the application
``config.Settings`` / Telegram / Mongo settings. It reads ``os.environ``
keys that start with ``AI_`` (after loading the project ``.env``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load project .env so AI_* works even when app ``config`` was not imported first.
# override=True so edits to ``.env`` take effect after process restart / reload.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

ChatProviderName = Literal[
    "ollama",
    "openrouter",
    "lmstudio",
    "openai_compatible",
    "local",
    "none",
]
EmbeddingProviderName = Literal[
    "ollama",
    "openrouter",
    "lmstudio",
    "openai_compatible",
    "local",
    "none",
]
VectorBackendName = Literal["mongodb", "qdrant", "memory", "none"]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class AISettings:
    """Immutable AI settings loaded from ``AI_*`` environment variables."""

    enabled: bool
    chat_provider: ChatProviderName
    chat_model: str
    embedding_provider: EmbeddingProviderName
    embedding_model: str
    api_base_url: str
    api_key: str
    vector_backend: VectorBackendName
    vector_collection: str
    vector_url: str
    request_timeout_seconds: float
    retry_max_attempts: int
    retry_backoff_seconds: float
    max_tokens: int
    daily_token_budget: int
    default_top_k: int
    prompts_dir: Path
    embed_batch_size: int
    chunk_max_chars: int
    chunk_overlap_chars: int
    index_message_batch_size: int
    rag_top_k: int
    rag_max_evidence_items: int
    rag_max_context_chars: int
    rag_context_token_budget: int
    rag_min_score: float
    entity_min_confidence: float
    entity_batch_size: int
    assistant_name: str
    assistant_history_turns: int
    assistant_session_collection: str
    report_collection: str
    model_cache_ttl_seconds: float = 300.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    http_referer: str = ""
    app_title: str = "Telegram Intelligence Platform"

    @property
    def is_configured_for_chat(self) -> bool:
        """Return True when chat provider/model look intentionally set."""
        return (
            self.enabled
            and self.chat_provider != "none"
            and bool(self.chat_model)
        )

    @property
    def is_configured_for_embeddings(self) -> bool:
        """Return True when embedding provider/model look intentionally set."""
        return (
            self.enabled
            and self.embedding_provider != "none"
            and bool(self.embedding_model)
        )

    @property
    def api_key_configured(self) -> bool:
        """True when AI_API_KEY or OPENROUTER_API_KEY is non-empty."""
        return bool(self.api_key.strip())

    @property
    def openrouter_api_key_valid(self) -> bool:
        """True when the configured key looks like an OpenRouter API key."""
        return looks_like_openrouter_api_key(self.api_key)


def looks_like_openrouter_api_key(key: str) -> bool:
    """OpenRouter keys are Bearer tokens starting with ``sk-or-``."""
    return (key or "").strip().startswith("sk-or-")


_ALLOWED_PROVIDERS = {
    "ollama",
    "openrouter",
    "lmstudio",
    "openai_compatible",
    "local",
    "none",
}


def _as_provider(value: str, kind: str) -> str:
    normalized = (value or "none").lower()
    if normalized not in _ALLOWED_PROVIDERS:
        raise ValueError(
            f"Invalid AI_{kind}_PROVIDER={value!r}. "
            f"Expected one of: {', '.join(sorted(_ALLOWED_PROVIDERS))}."
        )
    return normalized


def _as_vector_backend(value: str) -> VectorBackendName:
    normalized = (value or "none").lower()
    allowed = {"mongodb", "qdrant", "memory", "none"}
    if normalized not in allowed:
        raise ValueError(
            f"Invalid AI_VECTOR_BACKEND={value!r}. "
            f"Expected one of: {', '.join(sorted(allowed))}."
        )
    return normalized  # type: ignore[return-value]


def load_ai_settings() -> AISettings:
    """Load AI settings from the process environment (``AI_*`` only)."""
    # Re-read .env so key edits apply after provider refresh (no full restart).
    load_dotenv(_PROJECT_ROOT / ".env", override=True)
    package_prompts = Path(__file__).resolve().parent / "prompts"
    prompts_override = _env("AI_PROMPTS_DIR")
    prompts_dir = Path(prompts_override) if prompts_override else package_prompts

    return AISettings(
        enabled=_env_bool("AI_ENABLED", False),
        chat_provider=_as_provider(_env("AI_CHAT_PROVIDER", "none"), "CHAT"),  # type: ignore[arg-type]
        chat_model=_env("AI_CHAT_MODEL"),
        embedding_provider=_as_provider(
            _env("AI_EMBEDDING_PROVIDER", "none"),
            "EMBEDDING",
        ),  # type: ignore[arg-type]
        embedding_model=_env("AI_EMBEDDING_MODEL"),
        api_base_url=_env("AI_API_BASE_URL"),
        api_key=_env("AI_API_KEY") or _env("OPENROUTER_API_KEY"),
        ollama_base_url=_env("AI_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        or "http://127.0.0.1:11434",
        http_referer=_env("AI_HTTP_REFERER"),
        app_title=_env("AI_APP_TITLE", "Telegram Intelligence Platform")
        or "Telegram Intelligence Platform",
        vector_backend=_as_vector_backend(_env("AI_VECTOR_BACKEND", "none")),
        vector_collection=_env("AI_VECTOR_COLLECTION", "ai_embeddings"),
        vector_url=_env("AI_VECTOR_URL"),
        request_timeout_seconds=_env_float("AI_REQUEST_TIMEOUT_SECONDS", 30.0),
        retry_max_attempts=_env_int("AI_RETRY_MAX_ATTEMPTS", 3),
        retry_backoff_seconds=_env_float("AI_RETRY_BACKOFF_SECONDS", 0.5),
        max_tokens=_env_int("AI_MAX_TOKENS", 2048),
        daily_token_budget=_env_int("AI_DAILY_TOKEN_BUDGET", 0),
        default_top_k=_env_int("AI_DEFAULT_TOP_K", 8),
        prompts_dir=prompts_dir,
        embed_batch_size=_env_int("AI_EMBED_BATCH_SIZE", 32),
        chunk_max_chars=_env_int("AI_CHUNK_MAX_CHARS", 1200),
        chunk_overlap_chars=_env_int("AI_CHUNK_OVERLAP_CHARS", 150),
        index_message_batch_size=_env_int("AI_INDEX_MESSAGE_BATCH_SIZE", 100),
        rag_top_k=_env_int("AI_RAG_TOP_K", 8),
        rag_max_evidence_items=_env_int("AI_RAG_MAX_EVIDENCE_ITEMS", 8),
        rag_max_context_chars=_env_int("AI_RAG_MAX_CONTEXT_CHARS", 12000),
        rag_context_token_budget=_env_int("AI_RAG_CONTEXT_TOKEN_BUDGET", 3000),
        rag_min_score=_env_float("AI_RAG_MIN_SCORE", 0.0),
        entity_min_confidence=_env_float("AI_ENTITY_MIN_CONFIDENCE", 0.4),
        entity_batch_size=_env_int("AI_ENTITY_BATCH_SIZE", 50),
        assistant_name=_env("AI_ASSISTANT_NAME", "Sébastien")
        or "Sébastien",
        assistant_history_turns=_env_int("AI_ASSISTANT_HISTORY_TURNS", 8),
        assistant_session_collection=_env(
            "AI_ASSISTANT_SESSION_COLLECTION", "ai_sessions"
        )
        or "ai_sessions",
        report_collection=_env("AI_REPORT_COLLECTION", "ai_reports") or "ai_reports",
        model_cache_ttl_seconds=_env_float("AI_MODEL_CACHE_TTL_SECONDS", 300.0),
    )


@lru_cache(maxsize=1)
def get_ai_settings() -> AISettings:
    """Cached settings accessor. Call ``clear_ai_settings_cache`` in tests."""
    return load_ai_settings()


def reload_ai_settings() -> AISettings:
    """Drop cache and reload ``AI_*`` from ``.env`` (Control Center refresh)."""
    clear_ai_settings_cache()
    return get_ai_settings()


def clear_ai_settings_cache() -> None:
    """Drop the cached ``AISettings`` instance."""
    get_ai_settings.cache_clear()
