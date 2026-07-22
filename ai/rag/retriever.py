"""Vector retrieval + Mongo hydration for RAG.

The retriever embeds the analyst question, searches the vector store, then
loads supporting Mongo records. The LLM never receives a DB connection.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.providers.base import EmbeddingProvider
from ai.providers.errors import ProviderConfigurationError
from ai.rag.evidence import EvidenceItem
from ai.rag.mongo_loader import MongoEvidenceLoader
from ai.vectorstore.base import VectorStore
from ai.models.schemas import RetrievalHit

logger = logging.getLogger("ai.rag.retriever")


class Retriever:
    """Embed query → vector search → hydrate Mongo evidence."""

    def __init__(
        self,
        store: VectorStore,
        embedding_provider: EmbeddingProvider,
        *,
        embedding_model: str,
        evidence_loader: MongoEvidenceLoader | None = None,
        min_score: float = 0.0,
    ) -> None:
        if not embedding_model.strip():
            raise ProviderConfigurationError(
                "embedding_model is required for Retriever",
                provider=getattr(embedding_provider, "name", None),
                operation="retrieve",
            )
        self.store = store
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model.strip()
        self.evidence_loader = evidence_loader or MongoEvidenceLoader(db=None)
        self.min_score = float(min_score)

    def retrieve_evidence(
        self,
        question: str,
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[EvidenceItem]:
        """Return hydrated evidence for ``question``."""
        q = (question or "").strip()
        if not q:
            return []
        if top_k <= 0:
            return []

        embed = self.embedding_provider.embed([q], model=self.embedding_model)
        if not embed.vectors:
            raise ProviderConfigurationError(
                "Embedding provider returned no vectors for the question",
                provider=getattr(self.embedding_provider, "name", None),
                operation="retrieve",
            )
        query_vector = embed.vectors[0]
        hits = self.store.search(
            query_vector,
            top_k=top_k,
            filters=filters,
        )
        if self.min_score > 0:
            hits = [h for h in hits if float(h.score) >= self.min_score]

        evidence = self.evidence_loader.hydrate(hits)
        # Drop empty text evidence (cannot ground an answer).
        evidence = [item for item in evidence if item.text.strip()]
        logger.info(
            "rag_retrieve",
            extra={
                "ai_top_k": top_k,
                "ai_hit_count": len(evidence),
                "ai_embedding_model": self.embedding_model,
            },
        )
        return evidence

    def retrieve(
        self,
        question: str,
        *,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        """Backward-compatible list of ``RetrievalHit`` values."""
        evidence = self.retrieve_evidence(
            question, top_k=top_k, filters=filters
        )
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
