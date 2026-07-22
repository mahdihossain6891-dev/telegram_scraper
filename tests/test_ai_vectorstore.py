"""Tests for Phase 5 vector storage abstraction."""

from __future__ import annotations

import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.models.schemas import EmbeddingRecord
from ai.vectorstore import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorPoint,
    VectorStoreFactory,
    VectorStoreNotFoundError,
    build_qdrant_filter,
    create_vector_store,
    embedding_records_to_points,
)


def _settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    base = AISettings(
        enabled=True,
        chat_provider="none",
        chat_model="",
        embedding_provider="none",
        embedding_model="",
        api_base_url="",
        api_key="",
        vector_backend="memory",
        vector_collection="ai_vectors",
        vector_url="http://127.0.0.1:6333",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.01,
        max_tokens=128,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=Path("."),
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
        assistant_name='Investigation Assistant',
        assistant_history_turns=8,
        assistant_session_collection='ai_sessions',
        report_collection='ai_reports',
    )
    return replace(base, **kwargs) if kwargs else base


def test_memory_insert_update_delete_search_with_filters() -> None:
    store = InMemoryVectorStore()
    store.ensure_ready(dimension=3)

    assert (
        store.insert(
            [
                VectorPoint(id="a", vector=[1.0, 0.0, 0.0], payload={"chat_id": 1, "source_type": "message"}),
                VectorPoint(id="b", vector=[0.0, 1.0, 0.0], payload={"chat_id": 2, "source_type": "message"}),
                VectorPoint(id="c", vector=[0.9, 0.1, 0.0], payload={"chat_id": 1, "source_type": "message"}),
            ]
        )
        == 3
    )

    with pytest.raises(VectorStoreNotFoundError):
        store.insert([VectorPoint(id="a", vector=[1.0, 0.0, 0.0], payload={})])

    assert store.update([VectorPoint(id="b", vector=[0.0, 0.0, 1.0], payload={"chat_id": 2})]) == 1
    with pytest.raises(VectorStoreNotFoundError):
        store.update([VectorPoint(id="missing", vector=[1.0, 0.0, 0.0], payload={})])

    hits = store.search([1.0, 0.0, 0.0], top_k=5, filters={"chat_id": 1})
    assert [h.id for h in hits] == ["a", "c"]
    assert all(h.payload["chat_id"] == 1 for h in hits)

    assert store.delete(["a", "nope"]) == 1
    assert store.count() == 2


def test_factory_selects_memory_and_qdrant() -> None:
    mem = VectorStoreFactory(_settings(vector_backend="memory")).create()
    assert mem.name == "memory"
    qdrant = VectorStoreFactory(_settings(vector_backend="qdrant")).create()
    assert isinstance(qdrant, QdrantVectorStore)
    assert create_vector_store(_settings(vector_backend="none")).name == "none"


def test_embedding_record_adapter_is_optional_bridge() -> None:
    records = [
        EmbeddingRecord(
            chunk_id="msg:1",
            embedding_model="m",
            vector=[0.1, 0.2],
            metadata={"chat_id": 9},
            content_hash="abc",
            text="hello",
        )
    ]
    points = embedding_records_to_points(records)
    assert points[0].id == "msg:1"
    assert points[0].payload["chat_id"] == 9
    assert points[0].payload["text"] == "hello"


def test_build_qdrant_filter() -> None:
    assert build_qdrant_filter(None) is None
    assert build_qdrant_filter({"chat_id": 7}) == {
        "must": [{"key": "chat_id", "match": {"value": 7}}]
    }


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


def test_qdrant_upsert_and_search_http(monkeypatch: pytest.MonkeyPatch) -> None:
    store = QdrantVectorStore(url="http://127.0.0.1:6333", collection_name="demo")
    calls: list[tuple[str, str]] = []

    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        method = request.get_method()
        url = request.full_url
        calls.append((method, url))
        if method == "GET" and url.endswith("/collections/demo"):
            raise HTTPError(url, 404, "missing", hdrs=None, fp=BytesIO(b"{}"))
        if method == "PUT" and url.endswith("/collections/demo"):
            return _FakeResponse({"result": True})
        if method == "PUT" and "/points" in url:
            return _FakeResponse({"result": {"status": "ok"}})
        if method == "POST" and url.endswith("/points/search"):
            return _FakeResponse(
                {
                    "result": [
                        {
                            "id": "ignored-uuid",
                            "score": 0.99,
                            "payload": {"app_id": "p1", "chat_id": 1, "text": "hi"},
                        }
                    ]
                }
            )
        if method == "POST" and "/points/scroll" in url:
            return _FakeResponse({"result": {"points": []}})
        return _FakeResponse({"result": True})

    monkeypatch.setattr("ai.vectorstore.qdrant.urlopen", fake_urlopen)

    store.ensure_ready(dimension=2)
    n = store.upsert(
        [VectorPoint(id="p1", vector=[1.0, 0.0], payload={"chat_id": 1, "text": "hi"})]
    )
    assert n == 1
    hits = store.search([1.0, 0.0], top_k=3, filters={"chat_id": 1})
    assert len(hits) == 1
    assert hits[0].id == "p1"
    assert hits[0].payload["chat_id"] == 1
    assert any(method == "PUT" and "/points" in url for method, url in calls)
