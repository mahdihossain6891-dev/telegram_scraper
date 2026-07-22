"""SebastianService — enterprise intelligence assistant interface."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.core.orchestrator import AIOrchestrator, OrchestratorConfig
from ai.core.structured_response import StructuredResponse
from ai.investigation.assistant import AssistantTurnResult, InvestigationAssistant
from ai.investigation.context import InvestigationContext
from ai.investigation.session_store import SessionStore
from ai.models.schemas import Citation
from ai.prompts import PromptLoader
from ai.rag.pipeline import RAGPipeline
from ai.sessions.manager import InvestigationSessionManager

logger = logging.getLogger("ai.services.sebastian")


@dataclass(slots=True)
class SebastianResponse:
    """Complete Sébastien turn — structured + display answer."""

    session_id: str
    structured: StructuredResponse
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: str = "low"
    model: str = ""
    refused: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_assistant_result(self) -> AssistantTurnResult:
        return AssistantTurnResult(
            session_id=self.session_id,
            intent=self.structured.intent,
            intent_label=self.structured.intent_label,
            answer=self.answer,
            citations=list(self.citations),
            confidence=self.confidence,
            model=self.model,
            retrieved=list(self.structured.evidence),
            evidence=list(self.structured.evidence),
            refused=self.refused,
            metadata=self.metadata,
        )


class SebastianService:
    """High-level Sébastien interface — AI Intelligence Platform, not a chatbot."""

    def __init__(
        self,
        *,
        settings: AISettings | None = None,
        db: Any = None,
        rag: RAGPipeline | None = None,
        orchestrator: AIOrchestrator | None = None,
        session_manager: InvestigationSessionManager | None = None,
    ) -> None:
        self.settings = settings or get_ai_settings()
        self.db = db
        self.rag = rag or RAGPipeline.from_settings(self.settings, db=db)
        self._session_manager = session_manager or InvestigationSessionManager(
            SessionStore(
                db,
                collection_name=self.settings.assistant_session_collection,
                max_turns=self.settings.assistant_history_turns,
            )
        )
        self._session_manager.store.ensure_indexes()
        self._prompt_loader = PromptLoader(self.settings.prompts_dir)
        self._orchestrator = orchestrator or AIOrchestrator(
            OrchestratorConfig(
                db=db or self._resolve_db(),
                retriever=getattr(self.rag, "retriever", None),
                llm=getattr(self.rag, "llm", None),
                top_k=self.settings.rag_top_k or self.settings.default_top_k or 8,
            )
        )

    def _resolve_db(self) -> Any:
        loader = getattr(getattr(self.rag, "retriever", None), "evidence_loader", None)
        return getattr(loader, "db", None)

    @classmethod
    def from_settings(cls, settings: AISettings | None = None, *, db: Any = None) -> "SebastianService":
        return cls(settings=settings or get_ai_settings(), db=db)

    @property
    def orchestrator(self) -> AIOrchestrator:
        return self._orchestrator

    @property
    def tools(self) -> list[dict[str, Any]]:
        return self._orchestrator.list_tools()

    def investigate(
        self,
        question: str,
        *,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> SebastianResponse:
        """Run a full evidence-backed investigation turn."""
        session = self._session_manager.create(session_id=session_id, subject=subject)
        system_prompt = self._build_system_prompt(session)

        ctx, structured = self._orchestrator.run(
            question=question,
            session_id=session.session_id,
            session_subject=session.target,
            explicit_subject=subject,
            filters=filters,
            system_prompt=system_prompt,
            session_doc={"_id": session.session_id, "subject": session.target, "messages": session.history},
        )

        if ctx.subject and ctx.has_target() and not ctx.refused:
            self._session_manager.update_subject(session.session_id, ctx.subject)

        response = self._to_sebastian_response(ctx, structured, session.session_id)
        self._persist_turn(session.session_id, question, response)
        return response

    def create_legacy_assistant(
        self,
        *,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
    ) -> InvestigationAssistant:
        """Backward-compatible InvestigationAssistant using AIOrchestrator."""
        return InvestigationAssistant(
            self.rag,
            session_store=self._session_manager.store,
            session_id=session_id,
            subject=subject,
            settings=self.settings,
            prompt_loader=self._prompt_loader,
            tools=self._orchestrator.capability_registry.to_tool_registry(),
            db=self.db or self._resolve_db(),
            orchestrator=self._orchestrator,
        )

    def _build_system_prompt(self, session: Any) -> str:
        from ai.investigation.intents import classify_intent
        from ai.investigation.tools import DEFAULT_TOOL_POLICY

        history = self._session_manager.store.format_history(
            {"_id": session.session_id, "messages": session.history},
            max_turns=self.settings.assistant_history_turns,
        )
        rendered = self._prompt_loader.render(
            "investigation_assistant",
            version="latest",
            assistant_name=self.settings.assistant_name or "Sébastien",
            session_context=history,
            tool_policy=DEFAULT_TOOL_POLICY,
            intent_label="pending",
        )
        return rendered.text

    def _to_sebastian_response(
        self,
        ctx: InvestigationContext,
        structured: StructuredResponse,
        session_id: str,
    ) -> SebastianResponse:
        citations = [
            Citation(
                source_type=c.source_type,
                source_id=c.source_id,
                label=c.label,
                snippet=c.snippet,
            )
            for c in structured.citations
        ]
        conf = structured.confidence.get("label", "low") if structured.confidence else "low"
        return SebastianResponse(
            session_id=session_id,
            structured=structured,
            answer=ctx.answer or structured.executive_summary,
            citations=citations,
            confidence=str(conf),
            model=ctx.model,
            refused=structured.refused,
            metadata=structured.metadata,
        )

    def _persist_turn(self, session_id: str, question: str, response: SebastianResponse) -> None:
        self._session_manager.append_turn(session_id, role="user", content=question)
        self._session_manager.append_turn(
            session_id,
            role="assistant",
            content=response.answer,
            intent=response.structured.intent,
            citations=[
                {
                    "source_type": c.source_type,
                    "source_id": c.source_id,
                    "label": c.label,
                    "snippet": c.snippet,
                }
                for c in response.citations
            ],
            confidence=response.confidence,
            metadata={
                "refused": response.refused,
                "structured": response.structured.to_dict(),
                **response.metadata,
            },
        )
