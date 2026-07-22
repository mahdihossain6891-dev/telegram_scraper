"""Tests for Phase 6 RAG engine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.llm import LLMClient
from ai.models.schemas import QueryRequest
from ai.prompts import PromptLoader
from ai.providers.base import (
    ChatCompletion,
    ChatMessage,
    ChatModelProvider,
    EmbeddingProvider,
    EmbeddingResult,
)
from ai.rag import (
    ContextBuilder,
    MongoEvidenceLoader,
    RAGPipeline,
    Retriever,
    parse_rag_completion,
)
from ai.rag.evidence import EvidenceItem
from ai.vectorstore import InMemoryVectorStore, VectorPoint


class FakeEmbed(EmbeddingProvider):
    name = "fake-embed"

    def embed(self, texts, *, model=None, extra=None):
        # Map text length into a simple vector space aligned with upserted points.
        vectors = []
        for t in texts:
            if "night" in t.lower():
                vectors.append([1.0, 0.0, 0.0])
            elif "forward" in t.lower():
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return EmbeddingResult(vectors=vectors, model=model or "fake-embed")


class FakeChat(ChatModelProvider):
    name = "fake-chat"

    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        self.last_messages = list(messages)
        return ChatCompletion(
            content=(
                "1. Answer\n"
                "User 5 is active at night based on evidence [E1].\n\n"
                "2. Citations\n"
                "- [E1]\n\n"
                "3. Confidence\n"
                "high — strong score and direct match"
            ),
            model=model or "fake-chat",
            usage={"max_tokens": max_tokens},
        )


def _settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    base = AISettings(
        enabled=True,
        chat_provider="local",
        chat_model="fake-chat",
        embedding_provider="local",
        embedding_model="fake-embed",
        api_base_url="",
        api_key="",
        vector_backend="memory",
        vector_collection="ai_vectors",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.01,
        max_tokens=256,
        daily_token_budget=0,
        default_top_k=5,
        prompts_dir=Path(__file__).resolve().parents[1] / "ai" / "prompts",
        embed_batch_size=8,
        chunk_max_chars=400,
        chunk_overlap_chars=40,
        index_message_batch_size=50,
        rag_top_k=5,
        rag_max_evidence_items=3,
        rag_max_context_chars=2000,
        rag_context_token_budget=500,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=20,
        assistant_name='Investigation Assistant',
        assistant_history_turns=8,
        assistant_session_collection='ai_sessions',
        report_collection='ai_reports',
    )
    return replace(base, **kwargs) if kwargs else base


def test_context_builder_respects_budgets() -> None:
    builder = ContextBuilder(
        prompt_loader=PromptLoader(_settings().prompts_dir),
        max_evidence_items=2,
        max_context_chars=180,
        context_token_budget=80,
    )
    evidence = [
        EvidenceItem(
            chunk_id=f"c{i}",
            score=1.0 - i * 0.1,
            text=("word " * 40) + f" id={i}",
            citation_label=f"cite-{i}",
        )
        for i in range(5)
    ]
    selected = builder.select_evidence(evidence)
    assert 1 <= len(selected) <= 2
    block = builder.format_evidence_block(selected)
    assert "[E1]" in block
    prompt = builder.build_prompt_text("Who?", selected)
    assert "Who?" in prompt
    assert "word" in prompt


def test_parse_rag_completion_extracts_fields() -> None:
    evidence = [
        EvidenceItem(
            chunk_id="c1",
            score=0.9,
            text="night activity",
            source_type="message",
            source_id="1",
            citation_label="chat:1/msg:9",
        )
    ]
    parsed = parse_rag_completion(
        "1. Answer\nSeen at night [E1].\n2. Citations\n[E1]\n3. Confidence\nmedium — ok",
        evidence,
    )
    assert "night" in parsed.answer.lower()
    assert parsed.confidence == "medium"
    assert parsed.citations
    assert parsed.citations[0].source_id == "1"


def test_rag_pipeline_end_to_end(db_settings) -> None:
    settings_db, db_module = db_settings
    ai_settings = _settings()
    with db_module.get_session(settings_db) as session:
        session.messages.insert_one(
            {
                "_id": 42,
                "message_id": 9,
                "chat_id": 7,
                "sender_id": 5,
                "text": "Active every night between 2am and 4am.",
                "risk_score": 40,
                "risk_level": "Medium",
            }
        )

        store = InMemoryVectorStore()
        store.ensure_ready(dimension=3)
        store.upsert(
            [
                VectorPoint(
                    id="chunk-night",
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "text": "Active every night between 2am and 4am.",
                        "source_type": "message",
                        "source_id": "42",
                        "message_row_id": 42,
                        "chat_id": 7,
                        "message_id": 9,
                    },
                ),
                VectorPoint(
                    id="chunk-forward",
                    vector=[0.0, 1.0, 0.0],
                    payload={
                        "text": "Forwarded 300 messages today.",
                        "source_type": "message",
                        "message_row_id": 99,
                    },
                ),
            ]
        )

        chat = FakeChat()
        pipeline = RAGPipeline(
            retriever=Retriever(
                store,
                FakeEmbed(),
                embedding_model="fake-embed",
                evidence_loader=MongoEvidenceLoader(session.db),
            ),
            context_builder=ContextBuilder(
                prompt_loader=PromptLoader(ai_settings.prompts_dir),
                max_evidence_items=ai_settings.rag_max_evidence_items,
                max_context_chars=ai_settings.rag_max_context_chars,
                context_token_budget=ai_settings.rag_context_token_budget,
            ),
            llm=LLMClient(chat, default_model="fake-chat", default_max_tokens=128),
            settings=ai_settings,
        )

        result = pipeline.run(
            QueryRequest(question="Who is active at night?", top_k=3)
        )

        assert result.answer
        assert "night" in result.answer.lower() or "E1" in result.raw_completion
        assert result.confidence in {"high", "medium", "low"}
        assert result.retrieved
        assert result.evidence
        assert result.model == "fake-chat"
        # LLM saw prompt text, not a Mongo session / driver object
        user_content = chat.last_messages[-1].content
        assert "Active every night" in user_content
        assert "MongoClient" not in user_content
        assert "Collection" not in user_content
        # Hydrated citation metadata from Mongo
        assert any(
            item.metadata.get("message_row_id") == 42 for item in result.evidence
        )


def test_rag_empty_evidence_short_circuits() -> None:
    ai_settings = _settings()
    store = InMemoryVectorStore()
    store.ensure_ready(dimension=3)
    chat = FakeChat()
    pipeline = RAGPipeline(
        retriever=Retriever(
            store,
            FakeEmbed(),
            embedding_model="fake-embed",
            evidence_loader=MongoEvidenceLoader(db=None),
        ),
        context_builder=ContextBuilder(
            prompt_loader=PromptLoader(ai_settings.prompts_dir),
            max_evidence_items=2,
            max_context_chars=500,
            context_token_budget=200,
        ),
        llm=LLMClient(chat),
        settings=ai_settings,
    )
    result = pipeline.run(QueryRequest(question="anything?"))
    assert result.confidence == "low"
    assert "cannot answer" in result.answer.lower()
    assert chat.last_messages == []
