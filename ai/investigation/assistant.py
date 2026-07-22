"""Investigation Assistant — Sébastien investigation copilot.

Sébastien is not a chatbot. ``ask()`` runs the structured investigation
orchestrator; the LLM only explains an InvestigationContext.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.investigation.context import InvestigationContext
from ai.investigation.entity_resolution import EntityResolutionResult, EntityResolver
from ai.investigation.intents import InvestigationIntent, classify_intent
from ai.investigation.orchestrator import InvestigationOrchestrator, OrchestratorDeps
from ai.investigation.session_store import SessionStore
from ai.investigation.tools import (
    DEFAULT_TOOL_POLICY,
    ReadOnlyToolRegistry,
    default_tool_registry,
)
from ai.models.schemas import Citation, QueryResponse
from ai.prompts import PromptLoader
from ai.rag.pipeline import RAGPipeline

logger = logging.getLogger("ai.investigation.assistant")


@dataclass(slots=True)
class AssistantTurnResult:
    """One assistant turn including session identity and investigation payload."""

    session_id: str
    intent: str
    intent_label: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: str = "low"
    model: str = ""
    retrieved: list[Any] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    refused: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_query_response(self) -> QueryResponse:
        return QueryResponse(
            answer=self.answer,
            citations=list(self.citations),
            confidence=self.confidence,
            model=self.model,
            retrieved=list(self.retrieved),
            evidence=list(self.evidence),
            metadata={
                **self.metadata,
                "session_id": self.session_id,
                "intent": self.intent,
                "refused": self.refused,
            },
        )


class InvestigationAssistant:
    """Session-aware investigation copilot backed by the orchestrator."""

    def __init__(
        self,
        rag: RAGPipeline,
        *,
        session_store: SessionStore | None = None,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        settings: AISettings | None = None,
        prompt_loader: PromptLoader | None = None,
        tools: ReadOnlyToolRegistry | None = None,
        assistant_name: str | None = None,
        db: Any = None,
        orchestrator: Any | None = None,
    ) -> None:
        self.rag = rag
        self.settings = settings or get_ai_settings()
        self.session_store = session_store or SessionStore(
            max_turns=self.settings.assistant_history_turns
        )
        self.session_store.ensure_indexes()
        self.prompt_loader = prompt_loader or PromptLoader(self.settings.prompts_dir)
        self.assistant_name = (
            assistant_name
            or self.settings.assistant_name
            or "Sébastien"
        )
        self.db = db
        if self.db is None:
            loader = getattr(getattr(rag, "retriever", None), "evidence_loader", None)
            self.db = getattr(loader, "db", None)
        self.entity_resolver = EntityResolver(self.db)
        self.tools = tools or default_tool_registry(
            retriever=getattr(rag, "retriever", None)
        )
        session = self.session_store.get_or_create(session_id, subject=subject)
        self.session_id = str(session["_id"])
        self._ai_orchestrator = orchestrator
        if orchestrator is not None:
            self.orchestrator = orchestrator
        else:
            self.orchestrator = InvestigationOrchestrator(
                OrchestratorDeps(
                    db=self.db,
                    retriever=getattr(rag, "retriever", None),
                    llm=getattr(rag, "llm", None),
                    entity_resolver=self.entity_resolver,
                    tools=self.tools,
                    top_k=self.settings.rag_top_k or self.settings.default_top_k or 8,
                )
            )

    @classmethod
    def from_settings(
        cls,
        settings: AISettings | None = None,
        *,
        db=None,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        rag: RAGPipeline | None = None,
    ) -> "InvestigationAssistant":
        cfg = settings or get_ai_settings()
        pipeline = rag or RAGPipeline.from_settings(cfg, db=db)
        store = SessionStore(
            db,
            collection_name=cfg.assistant_session_collection,
            max_turns=cfg.assistant_history_turns,
        )
        return cls(
            pipeline,
            session_store=store,
            session_id=session_id,
            subject=subject,
            settings=cfg,
            db=db,
        )

    @property
    def session(self) -> dict[str, Any]:
        doc = self.session_store.get(self.session_id)
        return doc or {"_id": self.session_id, "messages": [], "subject": {}}

    def set_subject(self, subject: dict[str, Any]) -> None:
        """Update the investigation subject for subsequent retrieval filters."""
        self.session_store.update_subject(self.session_id, subject)

    def ask(
        self,
        question: str,
        *,
        filters: dict[str, Any] | None = None,
        subject: dict[str, Any] | None = None,
        deselected_tools: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AssistantTurnResult:
        """Run the structured investigation pipeline for one analyst turn."""
        session = self.session
        session_subject = dict(session.get("subject") or {})
        system_prompt = self._build_system_prompt(session, classify_intent(question or ""))

        ctx = self._run_orchestrator(
            question=question,
            session_subject=session_subject,
            explicit_subject=subject,
            filters=filters,
            system_prompt=system_prompt,
            session=session,
            deselected_tools=deselected_tools,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if ctx.subject and ctx.subject != session_subject and not ctx.refused:
            # Persist bound subject for multi-turn memory.
            if ctx.has_target():
                self.set_subject(ctx.subject)

        result = self._result_from_context(ctx)
        self._persist_turn(question or "", result)
        logger.info(
            "assistant_turn",
            extra={
                "ai_session_id": self.session_id,
                "ai_intent": result.intent,
                "ai_pipeline_status": ctx.status,
                "ai_refused": result.refused,
                "ai_confidence": result.confidence,
            },
        )
        return result

    def _run_orchestrator(
        self,
        *,
        question: str,
        session_subject: dict[str, Any],
        explicit_subject: dict[str, Any] | None,
        filters: dict[str, Any] | None,
        system_prompt: str,
        session: dict[str, Any],
        deselected_tools: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> InvestigationContext:
        if self._ai_orchestrator is not None:
            ctx, _structured = self._ai_orchestrator.run(
                question=question,
                session_id=self.session_id,
                session_subject=session_subject,
                explicit_subject=explicit_subject,
                filters=filters,
                system_prompt=system_prompt,
                session_doc=session,
            )
            return ctx
        return self.orchestrator.run(
            question=question,
            session_id=self.session_id,
            session_subject=session_subject,
            explicit_subject=explicit_subject,
            filters=filters,
            system_prompt=system_prompt,
            deselected_tools=deselected_tools,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _result_from_context(self, ctx: InvestigationContext) -> AssistantTurnResult:
        citations = [
            Citation(
                source_type=str(c.get("source_type") or "message"),
                source_id=str(c.get("source_id") or ""),
                label=str(c.get("label") or ""),
                snippet=str(c.get("snippet") or "")[:240],
            )
            for c in ctx.citations
        ]
        conf = "low"
        if ctx.confidence:
            conf = ctx.confidence.label
        meta = ctx.to_metadata()
        # Preserve entity_resolution shape expected by the UI.
        if ctx.entity_resolution:
            meta.setdefault("entity_resolution", ctx.entity_resolution)
            status = str(ctx.entity_resolution.get("status") or "")
            if ctx.status == "entity_ambiguous":
                meta["status"] = "Ambiguous Match"
            elif ctx.status == "entity_missing":
                meta["status"] = "No Match Found"
            elif ctx.status in {"target_required", "validation_failed", "unknown_intent"}:
                meta["status"] = "Target Required"
                meta["entity_resolution"] = {
                    **dict(ctx.entity_resolution),
                    "status": "target_required",
                    "suggestions": list(ctx.validation_suggestions),
                    "message": ctx.validation_message or ctx.answer,
                }
            elif status:
                meta.setdefault("status", status)

        evidence_payload = list(ctx.evidence or [])
        return AssistantTurnResult(
            session_id=self.session_id,
            intent=ctx.intent_key,
            intent_label=ctx.intent_label,
            answer=ctx.answer or "",
            citations=citations,
            confidence=conf,
            model=ctx.model,
            retrieved=evidence_payload,
            evidence=evidence_payload,
            refused=ctx.refused,
            metadata=meta,
        )

    def _build_system_prompt(
        self,
        session: dict[str, Any],
        intent: InvestigationIntent,
    ) -> str:
        history = self.session_store.format_history(
            session, max_turns=self.settings.assistant_history_turns
        )
        rendered = self.prompt_loader.render(
            "investigation_assistant",
            version="latest",
            assistant_name=self.assistant_name,
            session_context=history,
            tool_policy=DEFAULT_TOOL_POLICY,
            intent_label=f"{intent.key}: {intent.label}",
        )
        return rendered.text

    def _persist_turn(self, question: str, result: AssistantTurnResult) -> None:
        self.session_store.append_turn(
            self.session_id,
            role="user",
            content=question,
        )
        self.session_store.append_turn(
            self.session_id,
            role="assistant",
            content=result.answer,
            intent=result.intent,
            citations=[_citation_to_dict(c) for c in result.citations],
            confidence=result.confidence,
            metadata={
                "refused": result.refused,
                "entity_resolution": (result.metadata or {}).get("entity_resolution"),
                "pipeline_status": (result.metadata or {}).get("pipeline_status"),
                "next_actions": (result.metadata or {}).get("next_actions"),
                "confidence_detail": (result.metadata or {}).get("confidence_detail"),
            },
        )


def _citation_to_dict(citation: Citation) -> dict[str, Any]:
    return {
        "source_type": citation.source_type,
        "source_id": citation.source_id,
        "label": citation.label,
        "snippet": citation.snippet,
    }
