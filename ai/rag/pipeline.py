"""Retrieval-Augmented Generation pipeline.

Flow:
  question → embed/search vectors → hydrate Mongo evidence → build prompt
  → ChatModelProvider → answer + citations + confidence + evidence

The LLM never queries MongoDB. Mongo access stays inside ``MongoEvidenceLoader``.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.llm.client import LLMClient
from ai.models.schemas import Citation, QueryRequest, QueryResponse, RetrievalHit
from ai.prompts import PromptLoader
from ai.providers.base import ChatMessage, ChatModelProvider, EmbeddingProvider
from ai.providers.errors import ProviderConfigurationError
from ai.providers.factory import ProviderFactory
from ai.rag.context_builder import ContextBuilder
from ai.rag.evidence import EvidenceItem
from ai.rag.mongo_loader import MongoEvidenceLoader
from ai.rag.response_parser import heuristic_confidence, parse_rag_completion
from ai.rag.retriever import Retriever
from ai.vectorstore.base import VectorStore
from ai.vectorstore.factory import create_vector_store

logger = logging.getLogger("ai.rag.pipeline")

_EMPTY_ANSWER = (
    "I cannot answer from available data — no supporting evidence was retrieved."
)


class RAGPipeline:
    """End-to-end RAG engine (frontend-independent)."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        context_builder: ContextBuilder,
        llm: LLMClient,
        settings: AISettings | None = None,
        system_prompt: str = "",
    ) -> None:
        self.retriever = retriever
        self.context_builder = context_builder
        self.llm = llm
        self.settings = settings or get_ai_settings()
        self.system_prompt = system_prompt

    @classmethod
    def from_settings(
        cls,
        settings: AISettings | None = None,
        *,
        db=None,
        vector_store: VectorStore | None = None,
        chat_provider: ChatModelProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> "RAGPipeline":
        """Wire a pipeline from ``AI_*`` settings (optional Mongo ``db``)."""
        cfg = settings or get_ai_settings()
        if not cfg.is_configured_for_chat:
            raise ProviderConfigurationError(
                "Chat is not configured for RAG. Set AI_ENABLED, "
                "AI_CHAT_PROVIDER, and AI_CHAT_MODEL.",
                operation="rag",
            )
        if not cfg.is_configured_for_embeddings:
            raise ProviderConfigurationError(
                "Embeddings are not configured for RAG. Set AI_ENABLED, "
                "AI_EMBEDDING_PROVIDER, and AI_EMBEDDING_MODEL.",
                operation="rag",
            )

        factory = ProviderFactory(cfg)
        chat = chat_provider or factory.create_chat_provider()
        embed = embedding_provider or factory.create_embedding_provider()
        store = vector_store or create_vector_store(cfg, db=db)

        loader = MongoEvidenceLoader(db=db)
        retriever = Retriever(
            store,
            embed,
            embedding_model=cfg.embedding_model,
            evidence_loader=loader,
            min_score=cfg.rag_min_score,
        )
        context_builder = ContextBuilder(
            prompt_loader=PromptLoader(cfg.prompts_dir),
            max_evidence_items=cfg.rag_max_evidence_items,
            max_context_chars=cfg.rag_max_context_chars,
            context_token_budget=cfg.rag_context_token_budget,
        )
        llm = LLMClient(
            chat,
            default_model=cfg.chat_model,
            default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
            default_temperature=0.1,
        )
        return cls(
            retriever=retriever,
            context_builder=context_builder,
            llm=llm,
            settings=cfg,
        )

    def run(self, request: QueryRequest) -> QueryResponse:
        """Execute grounded Q&A for an analyst question."""
        question = (request.question or "").strip()
        if not question:
            return QueryResponse(
                answer="Question is empty.",
                citations=[],
                confidence="low",
                model="",
                retrieved=[],
                evidence=[],
            )

        top_k = request.top_k or self.settings.rag_top_k or self.settings.default_top_k
        top_k = max(1, min(int(top_k), self.settings.rag_max_evidence_items * 2))

        evidence = self.retriever.retrieve_evidence(
            question,
            top_k=top_k,
            filters=request.filters or None,
        )
        selected = self.context_builder.select_evidence(evidence)

        if not selected:
            return QueryResponse(
                answer=_EMPTY_ANSWER,
                citations=[],
                confidence="low",
                model="",
                retrieved=_to_retrieval_hits(evidence),
                evidence=evidence,
            )

        user_text = self.context_builder.build_prompt_text(question, selected)
        messages: list[ChatMessage] = []
        if self.system_prompt.strip():
            messages.append(
                ChatMessage(role="system", content=self.system_prompt.strip())
            )
        messages.append(ChatMessage(role="user", content=user_text))

        completion = self.llm.complete(
            messages,
            model=self.settings.chat_model or None,
            max_tokens=self.settings.max_tokens if self.settings.max_tokens > 0 else None,
        )
        parsed = parse_rag_completion(completion.content, selected)
        if not parsed.confidence:
            parsed.confidence = heuristic_confidence(selected, parsed.answer)

        logger.info(
            "rag_completed",
            extra={
                "ai_evidence": len(selected),
                "ai_confidence": parsed.confidence,
                "ai_model": completion.model,
                "ai_citations": len(parsed.citations),
            },
        )
        return QueryResponse(
            answer=parsed.answer,
            citations=parsed.citations,
            confidence=parsed.confidence,
            model=completion.model,
            retrieved=_to_retrieval_hits(selected),
            evidence=selected,
            raw_completion=completion.content,
            metadata={
                "confidence_note": parsed.raw_confidence_note,
                "top_k": top_k,
                "filters": dict(request.filters or {}),
            },
        )


def _to_retrieval_hits(evidence: list[EvidenceItem]) -> list[RetrievalHit]:
    return [
        RetrievalHit(
            chunk_id=item.chunk_id,
            score=item.score,
            text=item.text,
            metadata={
                **item.metadata,
                "source_type": item.source_type,
                "source_id": item.source_id,
                "citation_label": item.citation_label,
            },
        )
        for item in evidence
    ]
