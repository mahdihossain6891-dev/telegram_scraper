"""Tests for Phase 8 Investigation Assistant."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.investigation import (
    InvestigationAssistant,
    SessionStore,
    classify_intent,
)
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
from ai.rag import ContextBuilder, MongoEvidenceLoader, RAGPipeline, Retriever
from ai.vectorstore import InMemoryVectorStore, VectorPoint


class FakeEmbed(EmbeddingProvider):
    name = "fake-embed"

    def embed(self, texts, *, model=None, extra=None):
        vectors = []
        for t in texts:
            low = t.lower()
            if "risk" in low or "why" in low:
                vectors.append([1.0, 0.0, 0.0])
            elif "timeline" in low:
                vectors.append([0.0, 1.0, 0.0])
            elif "anomal" in low or "night" in low or "behav" in low:
                vectors.append([0.0, 0.0, 1.0])
            else:
                vectors.append([0.5, 0.5, 0.0])
        return EmbeddingResult(vectors=vectors, model=model or "fake-embed")


class FakeChat(ChatModelProvider):
    name = "fake-chat"

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        return ChatCompletion(
            content=(
                "1. Answer\n"
                "User shows elevated risk based on evidence [E1].\n\n"
                "2. Citations\n"
                "- [E1]\n\n"
                "3. Confidence\n"
                "high — direct evidence"
            ),
            model=model or "fake-chat",
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
        rag_max_evidence_items=5,
        rag_max_context_chars=4000,
        rag_context_token_budget=1000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=20,
        assistant_name="Test Assistant",
        assistant_history_turns=4,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
    )
    return replace(base, **kwargs) if kwargs else base


def _pipeline(store: InMemoryVectorStore, settings: AISettings) -> RAGPipeline:
    return RAGPipeline(
        retriever=Retriever(
            store,
            FakeEmbed(),
            embedding_model="fake-embed",
            evidence_loader=MongoEvidenceLoader(db=None),
        ),
        context_builder=ContextBuilder(
            prompt_loader=PromptLoader(settings.prompts_dir),
            max_evidence_items=settings.rag_max_evidence_items,
            max_context_chars=settings.rag_max_context_chars,
            context_token_budget=settings.rag_context_token_budget,
        ),
        llm=LLMClient(FakeChat(), default_model="fake-chat", default_max_tokens=128),
        settings=settings,
    )


@pytest.mark.parametrize(
    ("question", "intent_key"),
    [
        ("Why is this user high risk?", "high_risk"),
        ("Summarize this investigation", "summary"),
        ("Explain this relationship", "relationship"),
        ("Show behavioral anomalies", "behavioral_anomalies"),
        ("Generate a timeline", "timeline"),
    ],
)
def test_classify_supported_intents(question: str, intent_key: str) -> None:
    assert classify_intent(question).key == intent_key


def test_assistant_answers_with_citations_and_session_history() -> None:
    settings = _settings()
    store = InMemoryVectorStore()
    store.ensure_ready(dimension=3)
    store.upsert(
        [
            VectorPoint(
                id="risk-1",
                vector=[1.0, 0.0, 0.0],
                payload={
                    "text": "User 55 flagged for narcotics keyword and multi-group activity.",
                    "source_type": "message",
                    "source_id": "55",
                    "sender_id": 55,
                    "message_row_id": 1,
                },
            ),
            VectorPoint(
                id="night-1",
                vector=[0.0, 0.0, 1.0],
                payload={
                    "text": "Night activity spike between 02:00 and 04:00.",
                    "source_type": "message",
                    "sender_id": 55,
                    "message_row_id": 2,
                },
            ),
        ]
    )

    sessions = SessionStore(db=None, max_turns=4)
    assistant = InvestigationAssistant(
        _pipeline(store, settings),
        session_store=sessions,
        subject={"user_id": 55},
        settings=settings,
        prompt_loader=PromptLoader(settings.prompts_dir),
    )

    turn1 = assistant.ask("Why is this user high risk?")
    assert turn1.refused is False
    assert turn1.citations
    assert turn1.intent == "high_risk"
    assert "[E" in turn1.answer or turn1.citations

    turn2 = assistant.ask("Show behavioral anomalies")
    assert turn2.session_id == turn1.session_id
    assert turn2.intent == "behavioral_anomalies"

    session = assistant.session
    assert len(session["messages"]) >= 4  # user+assistant x2
    # Session history is separate from intelligence collections
    assert sessions.collection is None
    assert "messages" in session


def test_assistant_refuses_without_evidence() -> None:
    settings = _settings()
    store = InMemoryVectorStore()
    store.ensure_ready(dimension=3)
    assistant = InvestigationAssistant(
        _pipeline(store, settings),
        session_store=SessionStore(db=None),
        settings=settings,
        prompt_loader=PromptLoader(settings.prompts_dir),
    )
    result = assistant.ask("Summarize this investigation")
    assert result.refused is True
    assert "cannot answer" in result.answer.lower()
    assert "invent" in result.answer.lower()


def test_session_store_isolated_in_mongo(db_settings) -> None:
    settings_db, db_module = db_settings
    with db_module.get_session(settings_db) as session:
        store = SessionStore(session.db, max_turns=3)
        store.ensure_indexes()
        created = store.create(subject={"user_id": 9})
        store.append_turn(created["_id"], role="user", content="hello")
        store.append_turn(created["_id"], role="assistant", content="hi", citations=[])
        loaded = store.get(created["_id"])
        assert loaded is not None
        assert len(loaded["messages"]) == 2
        # Intelligence collections untouched
        assert session.messages.count_documents({}) == 0
        assert session.db["ai_sessions"].count_documents({}) == 1
