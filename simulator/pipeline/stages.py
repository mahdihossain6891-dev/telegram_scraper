"""Pipeline stage base and built-in stages (simulator-only stubs)."""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod

from simulator.pipeline.context import ProcessingContext


class BasePipelineStage(ABC):
    """Abstract pipeline stage with timing helper."""

    name: str

    @abstractmethod
    def _run(self, context: ProcessingContext) -> ProcessingContext: ...

    def process(self, context: ProcessingContext) -> ProcessingContext:
        start = time.perf_counter()
        try:
            result = self._run(context)
        finally:
            context.stage_durations_ms[self.name] = round((time.perf_counter() - start) * 1000, 3)
        return result


class ValidationStage(BasePipelineStage):
    name = "validation"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        if not context.event.text and not context.event.media_metadata:
            raise ValueError("Message must contain text or media metadata.")
        return context


class NormalizationStage(BasePipelineStage):
    name = "normalization"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        text = context.event.text.strip()
        text = re.sub(r"\s+", " ", text)
        context.normalized_text = text.lower()
        return context


class KeywordStage(BasePipelineStage):
    name = "keyword"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        from simulator.keywords import scan_simulation_text

        text = context.event.text or context.normalized_text
        keywords, categories = scan_simulation_text(text)
        context.keywords = keywords
        if categories:
            context.metrics["keyword_categories"] = categories
        return context


class EntityExtractionStage(BasePipelineStage):
    name = "entity_extraction"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        text = context.normalized_text
        if "@" in context.event.text:
            context.entities.append({"type": "mention", "value": "user"})
        if any(token in text for token in ("docker", "kubernetes", "python")):
            context.entities.append({"type": "technology", "value": "tech_term"})
        return context


class RiskStage(BasePipelineStage):
    name = "risk"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        score = min(1.0, len(context.keywords) * 0.15)
        categories = context.metrics.get("keyword_categories") or []
        if categories:
            score = max(score, 0.45 + 0.1 * len(categories))
        if "urgent" in context.keywords and "transfer" in context.keywords:
            score = max(score, 0.85)
        if any(cat in categories for cat in ("narcotics", "firearms", "human_trafficking")):
            score = max(score, 0.7)
        context.risk_score = round(score, 3)
        context.risk_level = (
            "critical" if score >= 0.85 else "high" if score >= 0.6 else "elevated" if score >= 0.3 else "normal"
        )
        return context


class BehaviorStage(BasePipelineStage):
    name = "behavior"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        context.behavior = {
            "sender_id": context.event.sender_id,
            "activity_score": min(1.0, 0.2 + len(context.event.text) / 200.0),
            "reply_depth": 1 if context.event.reply_to_message_id else 0,
        }
        return context


class RelationshipStage(BasePipelineStage):
    name = "relationship"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        if context.event.reply_to_message_id:
            context.relationships.append(
                {
                    "source": context.event.sender_id,
                    "target_chat": context.event.chat_id,
                    "kind": "reply",
                }
            )
        return context


class AlertStage(BasePipelineStage):
    name = "alert"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        if context.risk_level in {"high", "critical"}:
            context.alert = {
                "severity": context.risk_level,
                "keywords": list(context.keywords),
                "message_id": context.event.message_id,
            }
        return context


class PersistenceStage(BasePipelineStage):
    name = "persistence"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        # Simulator-only — no Mongo writes in Phase 7.
        context.persisted = True
        context.metrics["persisted_to"] = "simulator_memory"
        return context


class MetricsStage(BasePipelineStage):
    name = "metrics"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        context.metrics.update(
            {
                "processed": True,
                "stage_count": len(context.stage_durations_ms),
                "risk_level": context.risk_level,
            }
        )
        return context


class FutureStage(BasePipelineStage):
    """Placeholder for future OCR / AI / MITRE modules."""

    name = "future"

    def __init__(self, capability: str) -> None:
        self._capability = capability
        self.name = f"future_{capability}"

    def _run(self, context: ProcessingContext) -> ProcessingContext:
        context.metrics[self._capability] = "reserved"
        return context


def default_pipeline_stages() -> list[BasePipelineStage]:
    return [
        ValidationStage(),
        NormalizationStage(),
        KeywordStage(),
        EntityExtractionStage(),
        RiskStage(),
        BehaviorStage(),
        RelationshipStage(),
        AlertStage(),
        PersistenceStage(),
        MetricsStage(),
        FutureStage("ocr"),
        FutureStage("language_detection"),
        FutureStage("ai_classification"),
    ]
