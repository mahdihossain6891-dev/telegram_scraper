"""Async AI entity extraction job (out-of-band from scrape)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from pymongo.database import Database as MongoDatabase

from ai.config import AISettings, get_ai_settings
from ai.extraction.ner_service import NERService
from ai.extraction.service import EntityExtractionService
from ai.jobs.job_store import IndexCursorStore, JobStore
from ai.models.schemas import JobStatus
from ai.prompts import PromptLoader
from ai.providers.errors import ProviderConfigurationError, ProviderError
from ai.providers.factory import ProviderFactory

logger = logging.getLogger("ai.jobs.entity_extraction")

JOB_TYPE = "extract_entities"
CURSOR_KEY = "ai_entity_extraction"


class EntityExtractionJob:
    """Run AI entity extraction asynchronously without touching scrape paths."""

    def __init__(
        self,
        db: MongoDatabase,
        *,
        settings: AISettings | None = None,
        service: EntityExtractionService | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_ai_settings()
        self.job_store = JobStore(db)
        self.cursor_store = IndexCursorStore(db)
        self._service = service
        self._lock = threading.Lock()

    def _build_service(self) -> EntityExtractionService:
        if self._service is not None:
            return self._service
        if not self.settings.is_configured_for_chat:
            raise ProviderConfigurationError(
                "Chat provider required for AI entity extraction. "
                "Set AI_ENABLED, AI_CHAT_PROVIDER, and AI_CHAT_MODEL.",
                operation="entity_extraction",
            )
        provider = ProviderFactory(self.settings).create_chat_provider()
        ner = NERService(
            provider,
            model=self.settings.chat_model,
            prompt_loader=PromptLoader(self.settings.prompts_dir),
            max_tokens=self.settings.max_tokens if self.settings.max_tokens > 0 else 1024,
            min_confidence=self.settings.entity_min_confidence,
        )
        self._service = EntityExtractionService(self.db, ner)
        return self._service

    def run(
        self,
        *,
        full_rebuild: bool = False,
        limit: int | None = None,
        job_id: str | None = None,
    ) -> JobStatus:
        self.job_store.ensure_indexes()
        status = (
            self.job_store.get(job_id)
            if job_id
            else self.job_store.create(JOB_TYPE, detail="starting")
        )
        if status is None:
            status = self.job_store.create(JOB_TYPE, detail="starting")

        self.job_store.update(status.job_id, state="running", detail="extracting")
        stats: dict[str, Any] = {
            "messages_seen": 0,
            "ai_candidates": 0,
            "stored": 0,
            "matched_regex": 0,
            "full_rebuild": full_rebuild,
        }

        try:
            service = self._build_service()
            if full_rebuild:
                self.cursor_store.reset(key=CURSOR_KEY)
                after_row_id = None
            else:
                after_row_id = self.cursor_store.get_after_row_id(key=CURSOR_KEY)

            # Track max id while processing
            query: dict[str, Any] = {"text": {"$exists": True, "$nin": [None, ""]}}
            if after_row_id is not None:
                query["_id"] = {"$gt": after_row_id}

            max_row_id = after_row_id
            batch_size = self.settings.entity_batch_size
            processed = 0
            cursor = (
                self.db["messages"]
                .find(query)
                .sort([("_id", 1)])
                .batch_size(max(1, batch_size))
            )
            for doc in cursor:
                row_id = doc.get("_id")
                if isinstance(row_id, int):
                    max_row_id = row_id if max_row_id is None else max(max_row_id, row_id)
                result = service.process_message(doc)
                stats["messages_seen"] += 1
                stats["ai_candidates"] += result.get("ai_candidates", 0)
                stats["stored"] += result.get("stored", 0)
                stats["matched_regex"] += result.get("matched_regex", 0)
                processed += 1
                if limit is not None and processed >= limit:
                    break

            if max_row_id is not None:
                self.cursor_store.set_after_row_id(max_row_id, key=CURSOR_KEY)

            updated = self.job_store.update(
                status.job_id,
                state="completed",
                detail="ok",
                stats=stats,
            ) or status
            updated.stats = stats
            logger.info(
                "entity_extraction_completed",
                extra={"ai_job_id": updated.job_id, **{f"ai_{k}": v for k, v in stats.items()}},
            )
            return updated
        except (ProviderError, Exception) as exc:  # noqa: BLE001
            logger.exception("entity_extraction_failed")
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

    def start_async(
        self,
        *,
        full_rebuild: bool = False,
        limit: int | None = None,
    ) -> JobStatus:
        """Queue extraction on a daemon thread; returns immediately."""
        self.job_store.ensure_indexes()
        status = self.job_store.create(
            JOB_TYPE, detail="queued for background thread"
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
            name=f"ai-entities-{status.job_id[:8]}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "entity_extraction_async_started",
            extra={"ai_job_id": status.job_id},
        )
        return status
