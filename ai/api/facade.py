"""AI service facade for HTTP routes.

Routes talk only to this facade. The facade may open Mongo internally for
RAG evidence hydration / ``ai_*`` persistence, but never returns DB handles
or raw mongo documents to callers.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ai.api.serializers import (
    assistant_turn_dict,
    query_response_dict,
    report_dict,
)
from ai.config import AISettings, get_ai_settings
from ai.investigation.assistant import InvestigationAssistant
from ai.investigation.tools import build_rag_filters
from ai.models.schemas import QueryRequest
from ai.providers.errors import ProviderConfigurationError
from ai.rag.pipeline import RAGPipeline
from ai.reports.generator import ReportGenerator

logger = logging.getLogger("ai.api.facade")

DbFactory = Callable[[], Any]


def _default_db_factory() -> Any:
    """Resolve a Mongo database handle inside the AI package boundary."""
    from config import load_settings
    from database import get_db, init_db

    settings = load_settings()
    init_db(settings)
    return get_db(settings)


class AIServiceFacade:
    """Thin adapter between HTTP schemas and AI services."""

    def __init__(
        self,
        *,
        settings: AISettings | None = None,
        rag: RAGPipeline | None = None,
        report_generator: ReportGenerator | None = None,
        db_factory: DbFactory | None = None,
    ) -> None:
        self._settings = settings
        self._rag = rag
        self._report_generator = report_generator
        self._db_factory = db_factory
        self._db: Any = None

    @property
    def settings(self) -> AISettings:
        return self._settings or get_ai_settings()

    def health(self) -> dict[str, Any]:
        cfg = self.settings
        ready = bool(
            cfg.enabled
            and cfg.is_configured_for_chat
            and cfg.is_configured_for_embeddings
            and cfg.vector_backend != "none"
        )
        return {
            "status": "ok" if ready else ("disabled" if not cfg.enabled else "not_ready"),
            "enabled": cfg.enabled,
            "chat_configured": cfg.is_configured_for_chat,
            "embeddings_configured": cfg.is_configured_for_embeddings,
            "api_key_configured": cfg.api_key_configured,
            "chat_provider": cfg.chat_provider,
            "embedding_provider": cfg.embedding_provider,
            "vector_backend": cfg.vector_backend,
            "report_collection": cfg.report_collection,
            "session_collection": cfg.assistant_session_collection,
            "openrouter_key_valid": (
                cfg.openrouter_api_key_valid
                if cfg.chat_provider == "openrouter"
                else None
            ),
            "provider_hint": (
                "Set AI_API_KEY=sk-or-v1-... (or OPENROUTER_API_KEY) in .env, then refresh."
                if cfg.chat_provider == "openrouter" and not cfg.api_key_configured
                else (
                    "AI_API_KEY is set but invalid for OpenRouter — use sk-or-v1-... from "
                    "https://openrouter.ai/keys (not a hash or other token)."
                    if cfg.chat_provider == "openrouter"
                    and cfg.api_key_configured
                    and not cfg.openrouter_api_key_valid
                    else None
                )
            ),
        }

    def ensure_ready(self) -> None:
        """Raise if AI chat/embeddings/vector backend are not usable."""
        cfg = self.settings
        if not cfg.enabled:
            raise ProviderConfigurationError(
                "AI is disabled. Set AI_ENABLED=true to use /api/ai endpoints.",
                operation="api",
            )
        if not cfg.is_configured_for_chat:
            raise ProviderConfigurationError(
                "AI chat is not configured. Set AI_CHAT_PROVIDER and AI_CHAT_MODEL.",
                operation="api",
            )
        if not cfg.is_configured_for_embeddings:
            raise ProviderConfigurationError(
                "AI embeddings are not configured. "
                "Set AI_EMBEDDING_PROVIDER and AI_EMBEDDING_MODEL.",
                operation="api",
            )
        if cfg.vector_backend == "none":
            raise ProviderConfigurationError(
                "AI vector backend is not configured. Set AI_VECTOR_BACKEND.",
                operation="api",
            )

    def query(
        self,
        question: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.ensure_ready()
        pipeline = self._get_rag()
        result = pipeline.run(
            QueryRequest(
                question=question,
                top_k=top_k or 0,
                filters=dict(filters or {}),
            )
        )
        return query_response_dict(result)

    def summary(
        self,
        *,
        subject_id: str,
        subject_type: str = "user",
        subject_label: str | None = None,
        filters: dict[str, Any] | None = None,
        analyst_notes: str = "",
    ) -> dict[str, Any]:
        """Short subject summary via the Investigation Assistant (RAG-only)."""
        self.ensure_ready()
        label = subject_label or f"{subject_type}:{subject_id}"
        subject = _subject_dict(subject_type, subject_id, label)
        question = f"Summarize this investigation for {label}."
        if analyst_notes.strip():
            question = f"{question}\nAnalyst notes: {analyst_notes.strip()[:400]}"
        assistant = InvestigationAssistant.from_settings(
            self.settings,
            db=self._get_db(),
            subject=subject,
            rag=self._get_rag(),
        )
        turn = assistant.ask(question, filters=filters or None, subject=subject)
        payload = assistant_turn_dict(turn)
        payload["kind"] = "summary"
        return payload

    def report(
        self,
        *,
        report_type: str,
        subject_id: str,
        subject_type: str = "user",
        subject_label: str | None = None,
        filters: dict[str, Any] | None = None,
        analyst_notes: str = "",
        title: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        self.ensure_ready()
        generator = self._get_report_generator()
        result = generator.generate(
            report_type,
            subject_id=subject_id,
            subject_type=subject_type,
            subject_label=subject_label,
            filters=filters or None,
            analyst_notes=analyst_notes,
            persist=persist,
            title=title,
        )
        return report_dict(result)

    def investigate(
        self,
        question: str,
        *,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        deselected_tools: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        self.ensure_ready()
        assistant = InvestigationAssistant.from_settings(
            self.settings,
            db=self._get_db(),
            session_id=session_id,
            subject=subject or None,
            rag=self._get_rag(),
        )
        turn = assistant.ask(
            question,
            filters=filters or None,
            subject=subject or None,
            deselected_tools=deselected_tools or None,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        payload = assistant_turn_dict(turn)
        payload["kind"] = "investigate"
        return payload

    def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        self.ensure_ready()
        assistant = InvestigationAssistant.from_settings(
            self.settings,
            db=self._get_db(),
            session_id=session_id,
            subject=subject or None,
            rag=self._get_rag(),
        )
        turn = assistant.ask(
            message,
            filters=filters or None,
            subject=subject or None,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        payload = assistant_turn_dict(turn)
        payload["kind"] = "chat"
        return payload

    def planner_info(
        self,
        *,
        question: str | None = None,
        subject: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Describe the Investigation Planner and optionally preview a plan."""
        from ai.investigation.intents import classify_intent
        from ai.investigation.planner import InvestigationPlanner
        from ai.investigation.tools import default_tool_registry
        from ai.tools.capabilities import BUILTIN_CAPABILITIES
        from ai.tools.registry import CapabilityRegistry

        tools = default_tool_registry()
        caps = CapabilityRegistry.from_investigation_tools(tools)
        planner = InvestigationPlanner(caps)
        payload: dict[str, Any] = {
            "planner": "InvestigationPlanner",
            "description": (
                "Decides WHAT evidence is required and HOW to retrieve it via the "
                "Tool Registry. The LLM never queries the database."
            ),
            "pipeline": [
                "user_question",
                "intent_analysis",
                "investigation_planner",
                "execution_plan",
                "tool_registry",
                "evidence_collection",
                "evidence_validation",
                "context_builder",
                "llm_explain",
                "evidence_backed_response",
            ],
            "registered_tools": tools.list_tools(),
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "intents": list(c.intents),
                    "input_schema": dict(c.input_schema),
                    "output_schema": dict(c.output_schema),
                    "read_only": c.read_only,
                }
                for c in BUILTIN_CAPABILITIES
            ],
        }
        if question and question.strip():
            intent = classify_intent(question)
            payload["preview"] = planner.preview(
                intent,
                question=question,
                target=subject or {},
                available_tools=tools.list_tools(),
            )
        return payload

    def list_tools_catalog(self) -> dict[str, Any]:
        """List registered investigation tools and capabilities."""
        from ai.investigation.tools import default_tool_registry
        from ai.tools.capabilities import BUILTIN_CAPABILITIES
        from ai.tools.registry import CapabilityRegistry

        tools = default_tool_registry()
        caps = CapabilityRegistry.from_investigation_tools(tools)
        return {
            "tools": [
                {
                    "name": name,
                    "description": (
                        (caps.get_capability(name).description if caps.get_capability(name) else "")
                        or getattr(tools.get(name), "__doc__", "")
                        or name
                    ),
                    "capabilities": (
                        {
                            "input_schema": dict(caps.get_capability(name).input_schema),
                            "output_schema": dict(caps.get_capability(name).output_schema),
                            "intents": list(caps.get_capability(name).intents),
                            "read_only": caps.get_capability(name).read_only,
                        }
                        if caps.get_capability(name)
                        else {}
                    ),
                }
                for name in tools.list_tools()
            ],
            "catalog": [
                {
                    "name": c.name,
                    "description": c.description,
                    "intents": list(c.intents),
                    "input_schema": dict(c.input_schema),
                    "output_schema": dict(c.output_schema),
                }
                for c in BUILTIN_CAPABILITIES
            ],
        }

    def dismiss_session(self, session_id: str) -> dict[str, Any]:
        """Mark an ``ai_sessions`` record as dismissed. Never deletes intel data."""
        from ai.investigation.session_store import SessionStore

        cfg = self.settings
        store = SessionStore(
            self._get_db(),
            collection_name=cfg.assistant_session_collection,
            max_turns=cfg.assistant_history_turns,
        )
        doc = store.set_status(session_id, "dismissed")
        if not doc:
            raise ValueError(f"Session not found: {session_id}")
        return {
            "ok": True,
            "session_id": str(doc.get("_id") or session_id),
            "status": "dismissed",
            "dismissed_at": (
                doc.get("dismissed_at").isoformat()
                if hasattr(doc.get("dismissed_at"), "isoformat")
                else doc.get("dismissed_at")
            ),
        }

    def list_providers(self, *, refresh: bool = False) -> dict[str, Any]:
        """Catalog of providers with health — does not require full AI readiness."""
        from ai.config import reload_ai_settings
        from ai.providers.registry import get_model_registry

        if refresh:
            reload_ai_settings()
        return get_model_registry(self.settings).providers(refresh_health=refresh)

    def list_models(
        self,
        *,
        provider: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Discovered models for a provider — dynamic, never hardcoded."""
        from ai.config import reload_ai_settings
        from ai.providers.registry import get_model_registry

        if refresh:
            reload_ai_settings()
        return get_model_registry(self.settings).available_models(
            provider, refresh=refresh
        )

    def provider_health(
        self,
        *,
        provider: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Live provider health / latency / model count."""
        from ai.config import reload_ai_settings
        from ai.providers.registry import get_model_registry

        if refresh:
            reload_ai_settings()
        return get_model_registry(self.settings).provider_health(
            provider, refresh=refresh
        )

    def clear_model_cache(self, *, provider: str | None = None) -> dict[str, Any]:
        """Clear discovery cache only — never touches intel collections."""
        from ai.providers.registry import get_model_registry

        registry = get_model_registry(self.settings)
        if provider:
            registry.cache.invalidate(provider)
        else:
            registry.cache.invalidate()
        return {
            "ok": True,
            "provider": provider,
            "cache": registry.cache.stats(),
        }

    def test_provider(self, *, provider: str | None = None) -> dict[str, Any]:
        """Probe provider health (reconnect / test) without changing investigation state."""
        return self.provider_health(provider=provider, refresh=True)

    def reload_prompts(self) -> dict[str, Any]:
        """Reload prompt templates from disk into a fresh loader cache."""
        from ai.prompts import PromptLoader

        loader = PromptLoader(self.settings.prompts_dir)
        loader.clear_cache()
        ids = loader.list_prompt_ids()
        version = "unknown"
        try:
            if "investigation_assistant" in ids:
                version = f"investigation_assistant@{loader.latest_version('investigation_assistant')}"
            elif ids:
                pid = ids[0]
                version = f"{pid}@{loader.latest_version(pid)}"
        except Exception:  # noqa: BLE001 — soft metadata only
            version = "unknown"
        return {
            "ok": True,
            "prompt_ids": ids,
            "prompt_version": version,
            "prompts_dir": str(self.settings.prompts_dir),
        }

    def _active_db_cache_key(self) -> str | None:
        """Return a cache key when the console can switch databases at runtime."""
        if self._db_factory is not None:
            return None
        return "live"

    def _get_db(self) -> Any:
        cache_key = self._active_db_cache_key()
        if cache_key is not None:
            if self._db is not None and getattr(self, "_db_cache_key", None) == cache_key:
                return self._db
        elif self._db is not None:
            return self._db

        factory = self._db_factory
        if factory is None:
            if self._rag is not None and self._report_generator is not None:
                return None
            factory = _default_db_factory
        try:
            self._db = factory()
            if cache_key is not None:
                self._db_cache_key = cache_key
        except Exception:
            logger.warning("ai_api_db_unavailable", exc_info=True)
            self._db = None
            self._db_cache_key = None
        return self._db

    def _get_rag(self) -> RAGPipeline:
        if self._rag is not None and self._db_factory is not None:
            return self._rag
        cache_key = self._active_db_cache_key() or "default"
        if self._rag is not None and getattr(self, "_rag_cache_key", None) == cache_key:
            return self._rag
        self._rag = RAGPipeline.from_settings(self.settings, db=self._get_db())
        self._rag_cache_key = cache_key
        return self._rag

    def _get_report_generator(self) -> ReportGenerator:
        if self._report_generator is not None and self._db_factory is not None:
            return self._report_generator
        cache_key = self._active_db_cache_key() or "default"
        if (
            self._report_generator is not None
            and getattr(self, "_report_cache_key", None) == cache_key
        ):
            return self._report_generator
        rag = self._rag if getattr(self, "_rag_cache_key", None) == cache_key else None
        self._report_generator = ReportGenerator.from_settings(
            self.settings,
            db=self._get_db(),
            rag=rag,
        )
        self._report_cache_key = cache_key
        return self._report_generator


def _subject_dict(
    subject_type: str, subject_id: str, label: str
) -> dict[str, Any]:
    subject: dict[str, Any] = {
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        "display_name": label,
    }
    if subject_type in {"user", "personnel"} and str(subject_id).lstrip("-").isdigit():
        subject["user_id"] = int(subject_id)
    elif subject_type == "chat" and str(subject_id).lstrip("-").isdigit():
        subject["chat_id"] = int(subject_id)
    elif subject_type == "case":
        subject["case_id"] = str(subject_id)
    return subject


def filters_for_subject(
    subject_type: str, subject_id: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build vector filters for a subject without exposing DB access."""
    return build_rag_filters(subject=_subject_dict(subject_type, subject_id, subject_id), extra=extra)
