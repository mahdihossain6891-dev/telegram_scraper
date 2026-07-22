"""Tests for Phase 7 AI entity extraction."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.extraction import (
    AIEntityRepository,
    EntityExtractionService,
    EntityMergeService,
    NERService,
    normalize_entity_value,
)
from ai.jobs import EntityExtractionJob
from ai.prompts import PromptLoader
from ai.providers.base import ChatCompletion, ChatMessage, ChatModelProvider


class FakeEntityChat(ChatModelProvider):
    name = "fake-entity-chat"

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        text = messages[-1].content if messages else ""
        entities = []
        if "+1" in text or "555" in text:
            entities.append(
                {
                    "entity_type": "phone",
                    "entity_value": "+1 555 123 4567",
                    "confidence": 0.95,
                }
            )
        if "@" in text and "example.com" in text:
            entities.append(
                {
                    "entity_type": "email",
                    "entity_value": "ops@example.com",
                    "confidence": 0.9,
                }
            )
        if "http" in text:
            entities.append(
                {
                    "entity_type": "url",
                    "entity_value": "https://evil.example/path",
                    "confidence": 0.88,
                }
            )
        if "Acme" in text:
            entities.append(
                {
                    "entity_type": "organization",
                    "entity_value": "Acme Logistics",
                    "confidence": 0.7,
                }
            )
        if "Berlin" in text:
            entities.append(
                {
                    "entity_type": "location",
                    "entity_value": "Berlin",
                    "confidence": 0.8,
                }
            )
        if "0x" in text:
            entities.append(
                {
                    "entity_type": "wallet",
                    "entity_value": "0xabc123def4567890abc123def4567890abc123de",
                    "confidence": 0.85,
                }
            )
        if "@shadow" in text.lower() or "shadowops" in text.lower():
            entities.append(
                {
                    "entity_type": "username",
                    "entity_value": "@shadowops",
                    "confidence": 0.9,
                }
            )
        if "John Smith" in text:
            entities.append(
                {
                    "entity_type": "person",
                    "entity_value": "John Smith",
                    "confidence": 0.75,
                }
            )
        return ChatCompletion(
            content=json.dumps({"entities": entities}),
            model=model or "fake-entity-chat",
        )


def _settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    base = AISettings(
        enabled=True,
        chat_provider="local",
        chat_model="fake-entity-chat",
        embedding_provider="none",
        embedding_model="",
        api_base_url="",
        api_key="",
        vector_backend="none",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.01,
        max_tokens=512,
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
        assistant_name='Investigation Assistant',
        assistant_history_turns=8,
        assistant_session_collection='ai_sessions',
        report_collection='ai_reports',
    )
    return replace(base, **kwargs) if kwargs else base


def test_normalize_phone_and_username() -> None:
    assert normalize_entity_value("phone", "+1 (555) 123-4567") == "15551234567"
    assert normalize_entity_value("username", "@ShadowOps") == "shadowops"


def test_merge_flags_regex_overlap_without_dropping_ai() -> None:
    merger = EntityMergeService()
    regex = [{"entity_type": "phone", "entity_value": "+1 555 123 4567"}]
    from ai.extraction.models import AIEntityCandidate

    ai = [
        AIEntityCandidate(
            entity_type="phone",
            entity_value="+1-555-123-4567",
            confidence=0.9,
        ),
        AIEntityCandidate(
            entity_type="organization",
            entity_value="Acme Logistics",
            confidence=0.7,
        ),
    ]
    merged = merger.merge(regex, ai)
    assert len(merged) == 2
    phone = next(m for m in merged if m.entity_type == "phone")
    org = next(m for m in merged if m.entity_type == "organization")
    assert phone.matched_regex is True
    assert org.matched_regex is False


def test_extraction_writes_ai_entities_not_regex(db_settings) -> None:
    settings_db, db_module = db_settings
    ai_settings = _settings()
    with db_module.get_session(settings_db) as session:
        session.messages.insert_one(
            {
                "_id": 10,
                "message_id": 1,
                "chat_id": 100,
                "text": (
                    "Contact John Smith at +1 555 123 4567 or ops@example.com. "
                    "Org Acme Logistics in Berlin. Wallet 0xabc123def4567890abc123def4567890abc123de "
                    "see https://evil.example/path @shadowops"
                ),
            }
        )
        # Existing regex entity that must remain untouched.
        session.entities.insert_one(
            {
                "_id": 1,
                "message_row_id": 10,
                "entity_type": "phone",
                "entity_value": "+1 555 123 4567",
            }
        )
        regex_before = session.entities.count_documents({})

        ner = NERService(
            FakeEntityChat(),
            model="fake-entity-chat",
            prompt_loader=PromptLoader(ai_settings.prompts_dir),
            min_confidence=0.4,
        )
        service = EntityExtractionService(session.db, ner)
        stats = service.process_message(session.messages.find_one({"_id": 10}))

        assert stats["ai_candidates"] >= 5
        assert stats["stored"] >= 5
        assert stats["matched_regex"] >= 1
        assert session.entities.count_documents({}) == regex_before

        repo = AIEntityRepository(session.db)
        rows = repo.list_for_message(10)
        types = {r["entity_type"] for r in rows}
        assert "phone" in types
        assert "email" in types
        assert "organization" in types
        assert all("confidence" in r for r in rows)
        phone_ai = next(r for r in rows if r["entity_type"] == "phone")
        assert phone_ai["matched_regex"] is True


def test_entity_extraction_job_async(db_settings) -> None:
    settings_db, db_module = db_settings
    ai_settings = _settings()
    with db_module.get_session(settings_db) as session:
        session.messages.insert_one(
            {
                "_id": 20,
                "message_id": 2,
                "chat_id": 2,
                "text": "Email ops@example.com only.",
            }
        )
        ner = NERService(
            FakeEntityChat(),
            prompt_loader=PromptLoader(ai_settings.prompts_dir),
        )
        service = EntityExtractionService(session.db, ner)
        job = EntityExtractionJob(
            session.db, settings=ai_settings, service=service
        )
        queued = job.start_async()
        assert queued.state == "queued"
        deadline = time.time() + 5
        final = None
        while time.time() < deadline:
            final = job.job_store.get(queued.job_id)
            if final and final.state in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert final is not None
        assert final.state == "completed"
        assert AIEntityRepository(session.db).count() >= 1
