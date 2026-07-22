"""RAG-grounded structured report generation.

Reports are produced only from retrieved evidence. Artifacts are stored in
``ai_reports`` — never in operational intelligence collections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai.config import AISettings, get_ai_settings
from ai.investigation.tools import build_rag_filters
from ai.llm.client import LLMClient
from ai.models.schemas import Citation
from ai.prompts import PromptLoader
from ai.providers.base import ChatMessage, ChatModelProvider, EmbeddingProvider
from ai.rag.context_builder import ContextBuilder
from ai.rag.evidence import EvidenceItem
from ai.rag.pipeline import RAGPipeline
from ai.rag.retriever import Retriever
from ai.rag.user_enrichment import UserIdentityEnricher, format_username
from ai.reports.models import GeneratedReport, ReportSection
from ai.reports.parser import assemble_markdown, parse_report_completion
from ai.reports.repository import ReportRepository
from ai.reports.types import ReportType, ReportTypeSpec, format_section_outline, get_report_spec
from ai.vectorstore.base import VectorStore

logger = logging.getLogger("ai.reports.generator")

_REFUSAL_BODY = (
    "Insufficient retrieved evidence to generate this report. "
    "No claims were invented. Index relevant messages for RAG and retry."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReportGenerator:
    """Generate structured, citation-backed AI reports via RAG."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        llm: LLMClient,
        context_builder: ContextBuilder | None = None,
        prompt_loader: PromptLoader | None = None,
        repository: ReportRepository | None = None,
        settings: AISettings | None = None,
    ) -> None:
        self.settings = settings or get_ai_settings()
        self.retriever = retriever
        self.llm = llm
        self.prompt_loader = prompt_loader or PromptLoader(self.settings.prompts_dir)
        self.context_builder = context_builder or ContextBuilder(
            prompt_loader=self.prompt_loader,
            max_evidence_items=self.settings.rag_max_evidence_items,
            max_context_chars=self.settings.rag_max_context_chars,
            context_token_budget=self.settings.rag_context_token_budget,
        )
        self.repository = repository or ReportRepository(
            collection_name=self.settings.report_collection
        )
        self.repository.ensure_indexes()

    @classmethod
    def from_settings(
        cls,
        settings: AISettings | None = None,
        *,
        db=None,
        rag: RAGPipeline | None = None,
        vector_store: VectorStore | None = None,
        chat_provider: ChatModelProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        repository: ReportRepository | None = None,
    ) -> "ReportGenerator":
        """Wire a generator from ``AI_*`` settings (optional Mongo ``db``)."""
        cfg = settings or get_ai_settings()
        if rag is not None:
            return cls(
                retriever=rag.retriever,
                llm=rag.llm,
                context_builder=rag.context_builder,
                repository=repository
                or ReportRepository(db, collection_name=cfg.report_collection),
                settings=cfg,
            )

        pipeline = RAGPipeline.from_settings(
            cfg,
            db=db,
            vector_store=vector_store,
            chat_provider=chat_provider,
            embedding_provider=embedding_provider,
        )
        return cls(
            retriever=pipeline.retriever,
            llm=pipeline.llm,
            context_builder=pipeline.context_builder,
            repository=repository
            or ReportRepository(db, collection_name=cfg.report_collection),
            settings=cfg,
        )

    def generate(
        self,
        report_type: ReportType | str,
        *,
        subject_id: str,
        subject_type: str = "user",
        subject_label: str | None = None,
        filters: dict[str, Any] | None = None,
        analyst_notes: str = "",
        persist: bool = True,
        title: str | None = None,
    ) -> GeneratedReport:
        """Generate one structured report grounded in RAG evidence."""
        spec = get_report_spec(report_type)
        label = (subject_label or subject_id or "unknown").strip()
        resolved_subject_id = str(subject_id)

        if subject_type in {"user", "personnel"}:
            from ai.investigation.entity_resolution import EntityMention, EntityResolver

            db = getattr(self.retriever.evidence_loader, "db", None)
            resolution = EntityResolver(db).resolve_mention(
                EntityMention(
                    raw=str(subject_id),
                    kind_hint="user",
                    is_id=str(subject_id).lstrip("-").isdigit(),
                    is_username=str(subject_id).startswith("@"),
                ),
                query=str(subject_id),
            )
            if resolution.status in {"no_match", "ambiguous"}:
                report = self._entity_gate_report(
                    spec=spec,
                    title=title or f"Report: {subject_id}",
                    subject_type=subject_type,
                    subject_id=str(subject_id),
                    resolution=resolution,
                )
                if persist:
                    self.repository.save(report)
                return report
            if resolution.primary:
                resolved_subject_id = str(resolution.primary.entity_id)
                label = resolution.primary.label()
            elif str(subject_id).lstrip("-").isdigit():
                # Fallback enrichment for legacy paths.
                user = UserIdentityEnricher(db).lookup_one(int(subject_id))
                if user and user.get("display_name"):
                    pretty = str(user.get("display_name") or "").strip()
                    handle = format_username(user.get("username"))
                    label = (
                        f"{pretty} ({handle})"
                        if handle and handle not in pretty
                        else pretty
                    )

        report_title = title or spec.title_template.format(subject=label)
        subject_id = resolved_subject_id

        subject_filters = dict(filters or {})
        # Convenience: numeric subject_id as user filter when subject_type is user.
        if (
            subject_type in {"user", "personnel"}
            and "sender_id" not in subject_filters
            and str(subject_id).lstrip("-").isdigit()
        ):
            subject_filters = build_rag_filters(
                subject={"user_id": int(subject_id)},
                extra=subject_filters,
            )
        elif filters is None and subject_type == "chat" and str(subject_id).lstrip("-").isdigit():
            subject_filters = build_rag_filters(
                subject={"chat_id": int(subject_id)},
            )

        retrieval_q = self._retrieval_question(spec, label, subject_id, analyst_notes)
        top_k = self.settings.rag_top_k or self.settings.default_top_k
        evidence = self.retriever.retrieve_evidence(
            retrieval_q,
            top_k=top_k,
            filters=subject_filters or None,
        )
        selected = self.context_builder.select_evidence(evidence)

        if not selected:
            report = self._refusal_report(
                spec=spec,
                title=report_title,
                subject_type=subject_type,
                subject_id=str(subject_id),
                metadata={"filters": subject_filters, "retrieval_question": retrieval_q},
            )
            if persist:
                self.repository.save(report)
            return report

        evidence_block = self.context_builder.format_evidence_block(selected)
        prompt = self.prompt_loader.render(
            "structured_report",
            version="latest",
            report_type_label=spec.label,
            report_title=report_title,
            subject_label=label,
            subject_id=str(subject_id),
            section_outline=format_section_outline(spec),
            evidence_block=evidence_block,
            analyst_notes=analyst_notes.strip() or "(none)",
            citation_instructions=(
                "Every factual claim must cite retrieved evidence using [E#] labels. "
                "Never invent facts, scores, users, or relationships."
            ),
        )

        completion = self.llm.complete(
            [ChatMessage(role="user", content=prompt.text)],
            model=self.settings.chat_model or None,
            max_tokens=self.settings.max_tokens if self.settings.max_tokens > 0 else None,
        )
        parsed = parse_report_completion(
            completion.content,
            spec=spec,
            evidence=selected,
        )

        if not parsed.citations:
            # Mandatory citations when evidence exists.
            parsed.citations = [
                Citation(
                    source_type=item.source_type,
                    source_id=item.source_id,
                    label=f"E{i}:{item.citation_label or item.chunk_id}",
                    snippet=item.text[:240],
                )
                for i, item in enumerate(selected[:5], start=1)
            ]

        report = GeneratedReport(
            report_id=str(uuid4()),
            report_type=spec.report_type.value,
            title=report_title,
            subject_type=subject_type,
            subject_id=str(subject_id),
            sections=parsed.sections,
            citations=parsed.citations,
            confidence=parsed.confidence or "low",
            model=completion.model,
            body_markdown=parsed.body_markdown,
            refused=False,
            created_at=_utcnow(),
            metadata={
                "filters": subject_filters,
                "retrieval_question": retrieval_q,
                "evidence_count": len(selected),
                "confidence_note": parsed.raw_confidence_note,
            },
        )
        if persist:
            self.repository.save(report)
        logger.info(
            "ai_report_generated",
            extra={
                "ai_report_id": report.report_id,
                "ai_report_type": report.report_type,
                "ai_citations": len(report.citations),
                "ai_sections": len(report.sections),
            },
        )
        return report

    def generate_user_intelligence(
        self, user_id: int | str, **kwargs: Any
    ) -> GeneratedReport:
        return self.generate(
            ReportType.USER_INTELLIGENCE,
            subject_id=str(user_id),
            subject_type="user",
            subject_label=kwargs.pop("subject_label", f"user:{user_id}"),
            **kwargs,
        )

    def generate_investigation(
        self, subject_id: str, **kwargs: Any
    ) -> GeneratedReport:
        return self.generate(
            ReportType.INVESTIGATION,
            subject_id=str(subject_id),
            subject_type=kwargs.pop("subject_type", "investigation"),
            **kwargs,
        )

    def generate_case_summary(
        self, case_id: str, **kwargs: Any
    ) -> GeneratedReport:
        return self.generate(
            ReportType.CASE_SUMMARY,
            subject_id=str(case_id),
            subject_type=kwargs.pop("subject_type", "case"),
            subject_label=kwargs.pop("subject_label", f"case:{case_id}"),
            **kwargs,
        )

    def generate_behavioral_analysis(
        self, user_id: int | str, **kwargs: Any
    ) -> GeneratedReport:
        return self.generate(
            ReportType.BEHAVIORAL_ANALYSIS,
            subject_id=str(user_id),
            subject_type="user",
            subject_label=kwargs.pop("subject_label", f"user:{user_id}"),
            **kwargs,
        )

    def _retrieval_question(
        self,
        spec: ReportTypeSpec,
        label: str,
        subject_id: str,
        analyst_notes: str,
    ) -> str:
        parts = [
            spec.retrieval_question,
            f"Subject: {label} (id={subject_id})",
        ]
        if analyst_notes.strip():
            parts.append(f"Analyst notes: {analyst_notes.strip()[:500]}")
        return "\n".join(parts)

    def _entity_gate_report(
        self,
        *,
        spec: ReportTypeSpec,
        title: str,
        subject_type: str,
        subject_id: str,
        resolution: Any,
    ) -> GeneratedReport:
        status = (
            "No Match Found"
            if resolution.status == "no_match"
            else "Ambiguous Match"
        )
        body = resolution.format_answer()
        return GeneratedReport(
            report_id=str(uuid4()),
            report_type=spec.report_type.value,
            title=title,
            subject_type=subject_type,
            subject_id=subject_id,
            sections=[
                ReportSection(
                    section_id=resolution.status,
                    title=status,
                    body=body,
                    citation_labels=[],
                )
            ],
            citations=[],
            confidence="high",
            model="",
            body_markdown=body,
            refused=True,
            created_at=_utcnow(),
            metadata={
                **resolution.to_metadata(),
                "status": status,
                "reason": resolution.reason,
            },
        )

    def _refusal_report(
        self,
        *,
        spec: ReportTypeSpec,
        title: str,
        subject_type: str,
        subject_id: str,
        metadata: dict[str, Any],
    ) -> GeneratedReport:
        sections = [
            ReportSection(
                section_id=section.section_id,
                title=section.title,
                body=_REFUSAL_BODY if i == 0 else "Section omitted — no supporting evidence retrieved.",
                citation_labels=[],
            )
            for i, section in enumerate(spec.sections)
        ]
        body = assemble_markdown(title, sections, [], "low")
        return GeneratedReport(
            report_id=str(uuid4()),
            report_type=spec.report_type.value,
            title=title,
            subject_type=subject_type,
            subject_id=subject_id,
            sections=sections,
            citations=[],
            confidence="low",
            model="",
            body_markdown=body,
            refused=True,
            created_at=_utcnow(),
            metadata={**metadata, "reason": "insufficient_evidence"},
        )
