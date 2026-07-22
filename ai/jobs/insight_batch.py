"""Batch insight generation job stub."""

from __future__ import annotations

from ai.models.schemas import JobStatus


class InsightBatchJob:
    """Generates ``ai_insights`` for users/cases offline (future)."""

    def run(self, *, limit: int = 100) -> JobStatus:
        """Execute a batch insight pass.

        Raises:
            NotImplementedError: Always in Phase 1.
        """
        raise NotImplementedError(
            "InsightBatchJob.run is not implemented in Phase 1."
        )
