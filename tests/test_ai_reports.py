"""Tests for Phase 9 AI report generation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.llm import LLMClient
from ai.prompts import PromptLoader
from ai.providers.base import (
    ChatCompletion,
    ChatMessage,
    ChatModelProvider,
    EmbeddingProvider,
    EmbeddingResult,
)
from ai.rag import ContextBuilder, MongoEvidenceLoader, Retriever
from ai.reports import (
    ReportExporter,
    ReportGenerator,
    ReportRepository,
    ReportType,
    get_report_spec,
)
from ai.reports.parser import parse_report_completion
from ai.rag.evidence import EvidenceItem
from ai.vectorstore import InMemoryVectorStore, VectorPoint


class FakeEmbed(EmbeddingProvider):
    name = "fake-embed"

    def embed(self, texts, *, model=None, extra=None):
        return EmbeddingResult(
            vectors=[[1.0, 0.0, 0.0] for _ in texts],
            model=model or "fake-embed",
        )


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
                "## Executive summary\n"
                "User shows elevated risk based on narcotics keyword hits [E1].\n\n"
                "## Identity & profile\n"
                "Subject user_id=55 appears in flagged traffic [E1].\n\n"
                "## Activity overview\n"
                "Night activity noted in retrieved messages [E1].\n\n"
                "## Risk indicators\n"
                "Keyword-gated narcotics content elevates concern [E1].\n\n"
                "## Entities of interest\n"
                "No distinct wallet entities in evidence [E1].\n\n"
                "## Evidence index\n"
                "- [E1] flagged message\n\n"
                "## Confidence\n"
                "high — direct evidence match"
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
        assistant_name="Test Assistant",
        assistant_history_turns=4,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
    )
    return replace(base, **kwargs) if kwargs else base


def _generator(store: InMemoryVectorStore, settings: AISettings) -> ReportGenerator:
    retriever = Retriever(
        store,
        FakeEmbed(),
        embedding_model="fake-embed",
        evidence_loader=MongoEvidenceLoader(db=None),
    )
    return ReportGenerator(
        retriever=retriever,
        llm=LLMClient(FakeChat(), default_model="fake-chat", default_max_tokens=256),
        context_builder=ContextBuilder(
            prompt_loader=PromptLoader(settings.prompts_dir),
            max_evidence_items=settings.rag_max_evidence_items,
            max_context_chars=settings.rag_max_context_chars,
            context_token_budget=settings.rag_context_token_budget,
        ),
        prompt_loader=PromptLoader(settings.prompts_dir),
        repository=ReportRepository(db=None),
        settings=settings,
    )


@pytest.mark.parametrize(
    "report_type",
    [
        ReportType.USER_INTELLIGENCE,
        ReportType.INVESTIGATION,
        ReportType.CASE_SUMMARY,
        ReportType.BEHAVIORAL_ANALYSIS,
    ],
)
def test_report_specs_have_sections(report_type: ReportType) -> None:
    spec = get_report_spec(report_type)
    assert spec.sections
    assert all(s.section_id and s.title for s in spec.sections)


def test_parse_report_completion_maps_sections() -> None:
    spec = get_report_spec(ReportType.USER_INTELLIGENCE)
    evidence = [
        EvidenceItem(
            chunk_id="c1",
            score=0.9,
            text="narcotics keyword hit",
            source_type="message",
            source_id="1",
            citation_label="msg:1",
        )
    ]
    parsed = parse_report_completion(
        "## Executive summary\nRisk elevated [E1].\n"
        "## Identity & profile\nUser 55 [E1].\n"
        "## Confidence\nhigh — ok",
        spec=spec,
        evidence=evidence,
    )
    assert parsed.citations
    assert any(s.section_id == "executive_summary" for s in parsed.sections)
    assert "[E1]" in parsed.body_markdown or parsed.citations


def test_generate_user_report_with_citations_and_export(tmp_path: Path) -> None:
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
            )
        ]
    )
    gen = _generator(store, settings)
    report = gen.generate_user_intelligence(55, subject_label="user:55")
    assert report.refused is False
    assert report.citations
    assert report.sections
    assert report.report_type == ReportType.USER_INTELLIGENCE.value
    assert any("[E" in (s.body or "") or s.citation_labels for s in report.sections)

    loaded = gen.repository.get(report.report_id)
    assert loaded is not None
    assert loaded.report_id == report.report_id

    exporter = ReportExporter()
    md_path = exporter.export_markdown(report, tmp_path / "r.md")
    html_path = exporter.export_html(report, tmp_path / "r.html")
    assert md_path.read_text(encoding="utf-8").startswith("#")
    assert "<html" in html_path.read_text(encoding="utf-8").lower()
    with pytest.raises(NotImplementedError):
        exporter.export_pdf(report, tmp_path / "r.pdf")


def test_generate_refuses_without_evidence() -> None:
    settings = _settings()
    store = InMemoryVectorStore()
    store.ensure_ready(dimension=3)
    gen = _generator(store, settings)
    report = gen.generate_case_summary("case-1")
    assert report.refused is True
    assert "invent" in report.body_markdown.lower() or "insufficient" in report.body_markdown.lower()
    assert report.citations == []


def test_reports_isolated_from_intel_collections(db_settings) -> None:
    settings_db, db_module = db_settings
    with db_module.get_session(settings_db) as session:
        repo = ReportRepository(session.db)
        repo.ensure_indexes()
        settings = _settings()
        store = InMemoryVectorStore()
        store.ensure_ready(dimension=3)
        store.upsert(
            [
                VectorPoint(
                    id="x1",
                    vector=[1.0, 0.0, 0.0],
                    payload={
                        "text": "Investigation finding about subject link [forward].",
                        "source_type": "message",
                        "source_id": "9",
                        "sender_id": 9,
                    },
                )
            ]
        )
        gen = ReportGenerator(
            retriever=Retriever(
                store,
                FakeEmbed(),
                embedding_model="fake-embed",
                evidence_loader=MongoEvidenceLoader(db=None),
            ),
            llm=LLMClient(FakeChat(), default_model="fake-chat"),
            context_builder=ContextBuilder(
                prompt_loader=PromptLoader(settings.prompts_dir),
                max_evidence_items=5,
                max_context_chars=4000,
                context_token_budget=1000,
            ),
            prompt_loader=PromptLoader(settings.prompts_dir),
            repository=repo,
            settings=settings,
        )
        report = gen.generate_investigation("inv-1", subject_label="Investigation 1")
        assert session.db["ai_reports"].count_documents({}) == 1
        assert session.messages.count_documents({}) == 0
        assert repo.get(report.report_id) is not None


def test_structured_report_prompt_loads() -> None:
    loader = PromptLoader(_settings().prompts_dir)
    rendered = loader.render(
        "structured_report",
        report_type_label="Case Summary",
        report_title="Case Summary — 1",
        subject_label="case:1",
        subject_id="1",
        section_outline="1. Overview",
        evidence_block="[E1] demo",
        analyst_notes="none",
        citation_instructions="Cite [E#].",
    )
    assert "Case Summary" in rendered.text
    assert "[E1]" in rendered.text
