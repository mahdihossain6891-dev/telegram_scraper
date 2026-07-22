"""Asynchronous message-embedding indexer (out-of-band from scrape)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from pymongo.database import Database as MongoDatabase

from ai.config import AISettings, get_ai_settings
from ai.embeddings.chunking import ChunkingService
from ai.embeddings.message_source import FlaggedMessageSource
from ai.embeddings.repository import EmbeddingRepository
from ai.embeddings.service import EmbeddingService
from ai.jobs.job_store import IndexCursorStore, JobStore
from ai.models.schemas import JobStatus
from ai.providers.errors import ProviderConfigurationError, ProviderError
from ai.providers.factory import ProviderFactory

logger = logging.getLogger("ai.jobs.indexer")

JOB_TYPE = "index_embeddings"


class IndexerJob:
    """Read flagged messages → chunk → embed → store in ``ai_embeddings``.

    Designed to run in a background thread / separate process so Telethon
    scrape loops are never blocked.
    """

    def __init__(
        self,
        db: MongoDatabase,
        *,
        settings: AISettings | None = None,
        embedding_service: EmbeddingService | None = None,
        chunker: ChunkingService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_ai_settings()
        self.job_store = JobStore(db)
        self.cursor_store = IndexCursorStore(db)
        self.repository = EmbeddingRepository(
            db, collection_name=self.settings.vector_collection or "ai_embeddings"
        )
        self.source = FlaggedMessageSource(db)
        self.chunker = chunker or ChunkingService(
            max_chars=self.settings.chunk_max_chars,
            overlap_chars=self.settings.chunk_overlap_chars,
        )
        self._embedding_service = embedding_service
        self._lock = threading.Lock()

    def _service(self) -> EmbeddingService:
        if self._embedding_service is not None:
            return self._embedding_service
        if not self.settings.is_configured_for_embeddings:
            raise ProviderConfigurationError(
                "Embeddings are not configured. Set AI_ENABLED=true, "
                "AI_EMBEDDING_PROVIDER, and AI_EMBEDDING_MODEL.",
                provider=self.settings.embedding_provider,
                operation="index",
            )
        provider = ProviderFactory(self.settings).create_embedding_provider()
        self._embedding_service = EmbeddingService(
            provider,
            self.repository,
            embedding_model=self.settings.embedding_model,
            batch_size=self.settings.embed_batch_size,
        )
        return self._embedding_service

    def run(
        self,
        *,
        full_rebuild: bool = False,
        limit: int | None = None,
        job_id: str | None = None,
    ) -> JobStatus:
        """Run indexing synchronously (still separate from scrape)."""
        self.job_store.ensure_indexes()
        self.repository.ensure_indexes()

        status = (
            self.job_store.get(job_id)
            if job_id
            else self.job_store.create(JOB_TYPE, detail="starting")
        )
        if status is None:
            status = self.job_store.create(JOB_TYPE, detail="starting")

        self.job_store.update(status.job_id, state="running", detail="indexing")
        stats: dict[str, Any] = {
            "messages_seen": 0,
            "chunks_created": 0,
            "chunks_embedded": 0,
            "chunks_skipped_duplicate": 0,
            "records_written": 0,
            "full_rebuild": full_rebuild,
        }

        try:
            service = self._service()
            if full_rebuild:
                self.cursor_store.reset()
                after_row_id = None
            else:
                after_row_id = self.cursor_store.get_after_row_id()

            max_row_id = after_row_id
            pending_chunks = []
            message_batch = self.settings.index_message_batch_size

            for message in self.source.iter_messages(
                after_row_id=after_row_id,
                limit=limit,
                batch_size=message_batch,
            ):
                stats["messages_seen"] += 1
                row_id = message.get("_id")
                if isinstance(row_id, int):
                    max_row_id = row_id if max_row_id is None else max(max_row_id, row_id)

                chunks = self.chunker.chunk_message(
                    message, embedding_model=self.settings.embedding_model
                )
                stats["chunks_created"] += len(chunks)
                pending_chunks.extend(chunks)

                if len(pending_chunks) >= self.settings.embed_batch_size:
                    embedded, skipped, written = self._flush(service, pending_chunks)
                    stats["chunks_embedded"] += embedded
                    stats["chunks_skipped_duplicate"] += skipped
                    stats["records_written"] += written
                    pending_chunks = []

            if pending_chunks:
                embedded, skipped, written = self._flush(service, pending_chunks)
                stats["chunks_embedded"] += embedded
                stats["chunks_skipped_duplicate"] += skipped
                stats["records_written"] += written

            if max_row_id is not None and not full_rebuild:
                self.cursor_store.set_after_row_id(max_row_id)
            elif max_row_id is not None and full_rebuild:
                self.cursor_store.set_after_row_id(max_row_id)

            status = self.job_store.update(
                status.job_id,
                state="completed",
                detail="ok",
                stats=stats,
            ) or status
            status.stats = stats
            logger.info(
                "index_embeddings_completed",
                extra={"ai_job_id": status.job_id, **{f"ai_{k}": v for k, v in stats.items()}},
            )
            return status
        except (ProviderError, Exception) as exc:  # noqa: BLE001 — job boundary
            logger.exception("index_embeddings_failed")
            failed = self.job_store.update(
                status.job_id,
                state="failed",
                detail=str(exc),
                stats=stats,
            )
            if failed:
                failed.stats = stats
                return failed
            status.state = "failed"
            status.detail = str(exc)
            status.stats = stats
            return status

    def _flush(
        self,
        service: EmbeddingService,
        chunks: list,
    ) -> tuple[int, int, int]:
        before = len(chunks)
        prepared = service.prepare_chunks(chunks, skip_existing=True)
        skipped = before - len(prepared)
        if not prepared:
            return 0, skipped, 0
        # prepare_chunks already filtered; embed without a second dedup pass
        records = service.embed_chunks(
            prepared, skip_existing=False, persist=True
        )
        return len(records), skipped, len(records)

    def start_async(
        self,
        *,
        full_rebuild: bool = False,
        limit: int | None = None,
    ) -> JobStatus:
        """Queue work on a daemon thread; returns immediately with job id."""
        self.job_store.ensure_indexes()
        status = self.job_store.create(
            JOB_TYPE,
            detail="queued for background thread",
        )

        def _target() -> None:
            with self._lock:
                self.run(
                    full_rebuild=full_rebuild,
                    limit=limit,
                    job_id=status.job_id,
                )

        thread = threading.Thread(
            target=_target,
            name=f"ai-indexer-{status.job_id[:8]}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "index_embeddings_async_started",
            extra={"ai_job_id": status.job_id},
        )
        return status
