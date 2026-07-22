"""CLI / worker entry for AI jobs (never invoked from scrape loops)."""

from __future__ import annotations

import argparse
import logging
import sys

from ai.config import get_ai_settings
from ai.jobs.entity_extraction import EntityExtractionJob
from ai.jobs.indexer import IndexerJob
from ai.jobs.insight_batch import InsightBatchJob
from ai.models.schemas import JobStatus

logger = logging.getLogger("ai.jobs.runner")


class JobRunner:
    """Dispatches named AI jobs."""

    def __init__(self, db=None) -> None:
        self.db = db

    def _db(self):
        if self.db is not None:
            return self.db
        # Lazy import so importing ai.jobs does not require Mongo at import time.
        from database import get_session, init_db
        from config import load_settings

        settings = load_settings()
        init_db(settings)
        # Return a live DB handle; caller should keep process short-lived for CLI.
        from database import get_db

        return get_db(settings)

    def run(self, job_name: str, **kwargs: object) -> JobStatus:
        """Run ``job_name`` synchronously."""
        name = job_name.strip().lower()
        if name in {"index_embeddings", "index", "embeddings"}:
            full_rebuild = bool(kwargs.get("full_rebuild", False))
            limit = kwargs.get("limit")
            limit_i = int(limit) if limit is not None else None
            return IndexerJob(self._db(), settings=get_ai_settings()).run(
                full_rebuild=full_rebuild,
                limit=limit_i,
            )
        if name in {"extract_entities", "entities", "entity_extraction"}:
            full_rebuild = bool(kwargs.get("full_rebuild", False))
            limit = kwargs.get("limit")
            limit_i = int(limit) if limit is not None else None
            return EntityExtractionJob(self._db(), settings=get_ai_settings()).run(
                full_rebuild=full_rebuild,
                limit=limit_i,
            )
        if name in {"insight_batch", "insights"}:
            return InsightBatchJob().run(limit=int(kwargs.get("limit", 100)))
        raise ValueError(f"Unknown AI job: {job_name!r}")

    def start_async(self, job_name: str, **kwargs: object) -> JobStatus:
        """Start a job on a background thread (scrape-safe)."""
        name = job_name.strip().lower()
        if name in {"index_embeddings", "index", "embeddings"}:
            full_rebuild = bool(kwargs.get("full_rebuild", False))
            limit = kwargs.get("limit")
            limit_i = int(limit) if limit is not None else None
            return IndexerJob(self._db(), settings=get_ai_settings()).start_async(
                full_rebuild=full_rebuild,
                limit=limit_i,
            )
        if name in {"extract_entities", "entities", "entity_extraction"}:
            full_rebuild = bool(kwargs.get("full_rebuild", False))
            limit = kwargs.get("limit")
            limit_i = int(limit) if limit is not None else None
            return EntityExtractionJob(
                self._db(), settings=get_ai_settings()
            ).start_async(full_rebuild=full_rebuild, limit=limit_i)
        raise ValueError(f"Async not supported for job: {job_name!r}")


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m ai.jobs.runner index_embeddings [--full-rebuild]``."""
    parser = argparse.ArgumentParser(description="Run isolated AI jobs")
    parser.add_argument(
        "job",
        nargs="?",
        default="index_embeddings",
        help="Job name (default: index_embeddings)",
    )
    parser.add_argument("--full-rebuild", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="Start on a daemon thread and exit after queueing",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    runner = JobRunner()
    if args.async_mode:
        status = runner.start_async(
            args.job, full_rebuild=args.full_rebuild, limit=args.limit
        )
        print(f"queued job_id={status.job_id} state={status.state}")
        return 0

    status = runner.run(args.job, full_rebuild=args.full_rebuild, limit=args.limit)
    print(
        f"job_id={status.job_id} state={status.state} detail={status.detail} "
        f"stats={status.stats}"
    )
    return 0 if status.state == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
