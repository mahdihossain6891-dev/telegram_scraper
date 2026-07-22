"""Tests for Phase 4 embedding service + async indexer (isolated)."""

from __future__ import annotations

import time
from typing import Any, Sequence

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.embeddings import (
    ChunkingService,
    EmbeddingRepository,
    EmbeddingService,
    content_hash,
)
from ai.jobs import IndexerJob
from ai.models.schemas import AIDocumentChunk
from ai.providers.base import EmbeddingProvider, EmbeddingResult


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EmbeddingResult:
        self.calls.append(list(texts))
        vectors = [[float(len(t)), float(i), 0.5] for i, t in enumerate(texts)]
        return EmbeddingResult(vectors=vectors, model=model or "fake-model", usage={})


def _ai_settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    from pathlib import Path
    from dataclasses import replace

    base = AISettings(
        enabled=True,
        chat_provider="none",
        chat_model="",
        embedding_provider="local",
        embedding_model="fake-model",
        api_base_url="",
        api_key="",
        vector_backend="mongodb",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.01,
        max_tokens=128,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=Path("."),
        embed_batch_size=2,
        chunk_max_chars=80,
        chunk_overlap_chars=10,
        index_message_batch_size=10,
        rag_top_k=5,
        rag_max_evidence_items=5,
        rag_max_context_chars=4000,
        rag_context_token_budget=1000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=20,
        assistant_name='Investigation Assistant',
        assistant_history_turns=8,
        assistant_session_collection='ai_sessions',
        report_collection='ai_reports',
    )
    return replace(base, **kwargs) if kwargs else base


def test_content_hash_stable() -> None:
    assert content_hash("Hello  World", embedding_model="m") == content_hash(
        "hello world", embedding_model="m"
    )
    assert content_hash("a", embedding_model="m1") != content_hash("a", embedding_model="m2")


def test_chunking_splits_long_text() -> None:
    chunker = ChunkingService(max_chars=60, overlap_chars=10, min_chars=5)
    text = "Sentence one is here. " * 20
    chunks = chunker.chunk_text(
        text, source_type="message", source_id="1", embedding_model="m"
    )
    assert len(chunks) >= 2
    assert all(c.metadata.get("content_hash") for c in chunks)


def test_embedding_service_batch_and_dedup(db_settings) -> None:
    settings, db_module = db_settings
    provider = FakeEmbeddingProvider()
    with db_module.get_session(settings) as session:
        repo = EmbeddingRepository(session.db)
        repo.ensure_indexes()
        service = EmbeddingService(
            provider, repo, embedding_model="fake-model", batch_size=2
        )
        chunks = [
            AIDocumentChunk(
                chunk_id="c1",
                source_type="message",
                source_id="1",
                text="alpha message",
                metadata={},
            ),
            AIDocumentChunk(
                chunk_id="c2",
                source_type="message",
                source_id="2",
                text="beta message",
                metadata={},
            ),
            AIDocumentChunk(
                chunk_id="c3",
                source_type="message",
                source_id="3",
                text="gamma message",
                metadata={},
            ),
        ]
        first = service.embed_chunks(chunks)
        assert len(first) == 3
        assert len(provider.calls) == 2  # batch size 2 → 2+1
        assert repo.count(embedding_model="fake-model") == 3

        provider.calls.clear()
        second = service.embed_chunks(chunks)
        assert second == []
        assert provider.calls == []


def test_indexer_reads_messages_and_skips_duplicates(db_settings) -> None:
    settings_db, db_module = db_settings
    ai_settings = _ai_settings()
    provider = FakeEmbeddingProvider()
    with db_module.get_session(settings_db) as session:
        session.messages.insert_many(
            [
                {
                    "_id": 1,
                    "message_id": 10,
                    "chat_id": 100,
                    "sender_id": 5,
                    "text": "Flagged narcotics mention in group.",
                    "risk_score": 40,
                    "risk_level": "Medium",
                },
                {
                    "_id": 2,
                    "message_id": 11,
                    "chat_id": 100,
                    "sender_id": 5,
                    "text": "Another flagged firearms note.",
                    "risk_score": 55,
                    "risk_level": "High",
                },
                {
                    "_id": 3,
                    "message_id": 12,
                    "chat_id": 100,
                    "text": "",
                },
            ]
        )
        repo = EmbeddingRepository(session.db)
        service = EmbeddingService(
            provider, repo, embedding_model="fake-model", batch_size=10
        )
        job = IndexerJob(
            session.db,
            settings=ai_settings,
            embedding_service=service,
            chunker=ChunkingService(max_chars=200, overlap_chars=20),
        )
        status = job.run()
        assert status.state == "completed"
        assert status.stats["messages_seen"] == 2
        assert status.stats["chunks_embedded"] >= 2
        assert repo.count() >= 2

        provider.calls.clear()
        status2 = job.run()
        assert status2.state == "completed"
        # Incremental cursor → no new messages
        assert status2.stats["messages_seen"] == 0


def test_indexer_async_does_not_block(db_settings) -> None:
    settings_db, db_module = db_settings
    ai_settings = _ai_settings()
    provider = FakeEmbeddingProvider()
    with db_module.get_session(settings_db) as session:
        session.messages.insert_one(
            {
                "_id": 99,
                "message_id": 1,
                "chat_id": 1,
                "text": "Async index me please.",
            }
        )
        service = EmbeddingService(
            provider,
            EmbeddingRepository(session.db),
            embedding_model="fake-model",
            batch_size=8,
        )
        job = IndexerJob(session.db, settings=ai_settings, embedding_service=service)
        queued = job.start_async()
        assert queued.state == "queued"
        # Wait briefly for daemon thread
        deadline = time.time() + 5
        final = None
        while time.time() < deadline:
            final = job.job_store.get(queued.job_id)
            if final and final.state in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert final is not None
        assert final.state == "completed"
