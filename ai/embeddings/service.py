"""Embedding orchestration — batch embed with hash-based deduplication."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from ai.embeddings.hashing import content_hash
from ai.embeddings.repository import EmbeddingRepository
from ai.models.schemas import AIDocumentChunk, EmbeddingRecord
from ai.providers.base import EmbeddingProvider
from ai.providers.errors import ProviderConfigurationError

logger = logging.getLogger("ai.embeddings.service")


class EmbeddingService:
    """Coordinates chunk embedding via an ``EmbeddingProvider``."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        repository: EmbeddingRepository | None = None,
        *,
        embedding_model: str,
        batch_size: int = 32,
    ) -> None:
        if not embedding_model.strip():
            raise ProviderConfigurationError(
                "embedding_model is required for EmbeddingService",
                provider=getattr(provider, "name", None),
                operation="embed",
            )
        self.provider = provider
        self.repository = repository
        self.embedding_model = embedding_model.strip()
        self.batch_size = max(1, int(batch_size))

    def prepare_chunks(
        self,
        chunks: Sequence[AIDocumentChunk],
        *,
        skip_existing: bool = True,
    ) -> list[AIDocumentChunk]:
        """Attach content hashes and optionally drop already-indexed chunks."""
        prepared: list[AIDocumentChunk] = []
        for chunk in chunks:
            text = (chunk.text or "").strip()
            if not text:
                continue
            digest = content_hash(text, embedding_model=self.embedding_model)
            meta = dict(chunk.metadata or {})
            meta["content_hash"] = digest
            meta.setdefault("source_type", chunk.source_type)
            meta.setdefault("source_id", chunk.source_id)
            meta["text"] = text
            prepared.append(
                AIDocumentChunk(
                    chunk_id=chunk.chunk_id,
                    source_type=chunk.source_type,
                    source_id=chunk.source_id,
                    text=text,
                    metadata=meta,
                )
            )

        if not skip_existing or self.repository is None or not prepared:
            return prepared

        hashes = [str(c.metadata.get("content_hash")) for c in prepared]
        existing = self.repository.existing_hashes(
            hashes, embedding_model=self.embedding_model
        )
        filtered = [
            c
            for c in prepared
            if str(c.metadata.get("content_hash")) not in existing
        ]
        logger.info(
            "embedding_dedup",
            extra={
                "ai_candidates": len(prepared),
                "ai_existing": len(prepared) - len(filtered),
                "ai_to_embed": len(filtered),
                "ai_embedding_model": self.embedding_model,
            },
        )
        return filtered

    def embed_chunks(
        self,
        chunks: Sequence[AIDocumentChunk],
        *,
        skip_existing: bool = True,
        persist: bool = True,
    ) -> list[EmbeddingRecord]:
        """Embed chunks in batches and optionally persist to the repository."""
        pending = self.prepare_chunks(chunks, skip_existing=skip_existing)
        if not pending:
            return []

        records: list[EmbeddingRecord] = []
        for start in range(0, len(pending), self.batch_size):
            batch = pending[start : start + self.batch_size]
            texts = [c.text for c in batch]
            logger.info(
                "embedding_batch_start",
                extra={
                    "ai_batch_size": len(batch),
                    "ai_batch_offset": start,
                    "ai_embedding_model": self.embedding_model,
                },
            )
            result = self.provider.embed(texts, model=self.embedding_model)
            if len(result.vectors) != len(batch):
                raise ProviderConfigurationError(
                    f"Provider returned {len(result.vectors)} vectors for "
                    f"{len(batch)} texts",
                    provider=getattr(self.provider, "name", None),
                    operation="embed",
                )
            used_model = result.model or self.embedding_model
            for chunk, vector in zip(batch, result.vectors, strict=True):
                meta = dict(chunk.metadata)
                meta["provider"] = getattr(self.provider, "name", None)
                meta["usage"] = dict(result.usage or {})
                records.append(
                    EmbeddingRecord(
                        chunk_id=chunk.chunk_id,
                        embedding_model=used_model,
                        vector=list(vector),
                        metadata=meta,
                        content_hash=str(meta.get("content_hash") or ""),
                        text=chunk.text,
                    )
                )

        if persist and self.repository is not None and records:
            written = self.repository.upsert_records(records)
            logger.info(
                "embedding_batch_persisted",
                extra={
                    "ai_records": len(records),
                    "ai_written": written,
                    "ai_embedding_model": self.embedding_model,
                },
            )
        return records

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        metadata: dict[str, Any] | None = None,
        skip_existing: bool = True,
        persist: bool = False,
    ) -> list[EmbeddingRecord]:
        """Convenience wrapper for ad-hoc text lists (no RAG)."""
        base = dict(metadata or {})
        chunks = [
            AIDocumentChunk(
                chunk_id=f"adhoc:{i}:{content_hash(t, embedding_model=self.embedding_model)[:12]}",
                source_type=str(base.get("source_type") or "adhoc"),
                source_id=str(base.get("source_id") or i),
                text=t,
                metadata=dict(base),
            )
            for i, t in enumerate(texts)
            if (t or "").strip()
        ]
        return self.embed_chunks(
            chunks, skip_existing=skip_existing, persist=persist
        )
