"""AIOrchestrator — Sébastien's enterprise intelligence brain."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ai.cache.semantic import SemanticCache
from ai.core.observability import ObservabilityTracker
from ai.core.structured_response import StructuredResponse
from ai.core.types import PlatformEnvironment
from ai.evidence.engine import EvidenceEngine
from ai.investigation.context import InvestigationContext
from ai.investigation.orchestrator import InvestigationOrchestrator, OrchestratorDeps
from ai.investigation.tools import build_investigation_tools
from ai.memory.manager import MemoryManager
from ai.reasoning.engine import ReasoningEngine
from ai.security.policy import EnvironmentGuard, ReadOnlyPolicy
from ai.tools.registry import CapabilityRegistry
from ai.tools.router import ToolRouter

logger = logging.getLogger("ai.core.orchestrator")


@dataclass(slots=True)
class OrchestratorConfig:
    """Injectable dependencies for the AI orchestrator."""

    db: Any = None
    retriever: Any = None
    llm: Any = None
    top_k: int = 8
    cache_ttl: float = 1800.0


class AIOrchestrator:
    """Coordinates investigation, evidence, reasoning, and structured responses.

    Sébastian never queries databases directly — tools and RAG retrieve data.
    The LLM only explains structured, evidence-backed context.
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        *,
        capability_registry: CapabilityRegistry | None = None,
        evidence_engine: EvidenceEngine | None = None,
        reasoning_engine: ReasoningEngine | None = None,
        memory: MemoryManager | None = None,
        cache: SemanticCache | None = None,
        observability: ObservabilityTracker | None = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._capabilities = capability_registry or self._build_default_registry()
        self._tool_router = ToolRouter(self._capabilities)
        self._evidence_engine = evidence_engine or EvidenceEngine()
        self._reasoning_engine = reasoning_engine or ReasoningEngine()
        self._memory = memory or MemoryManager()
        self._cache = cache or SemanticCache()
        self._observability = observability or ObservabilityTracker()

        tool_registry = self._capabilities.to_tool_registry()
        self._investigation = InvestigationOrchestrator(
            OrchestratorDeps(
                db=self._config.db,
                retriever=self._config.retriever,
                llm=self._config.llm,
                tools=tool_registry,
                top_k=self._config.top_k,
            )
        )

    @property
    def capability_registry(self) -> CapabilityRegistry:
        return self._capabilities

    @property
    def tool_router(self) -> ToolRouter:
        return self._tool_router

    @property
    def observability(self) -> ObservabilityTracker:
        return self._observability

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": cap.name,
                "description": cap.description,
                "intents": list(cap.intents),
                "read_only": cap.read_only,
            }
            for cap in self._capabilities.list_capabilities()
        ]

    def run(
        self,
        *,
        question: str,
        session_id: str,
        session_subject: dict[str, Any] | None = None,
        explicit_subject: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        system_prompt: str = "",
        session_doc: dict[str, Any] | None = None,
    ) -> tuple[InvestigationContext, StructuredResponse]:
        """Execute full AI orchestration pipeline."""
        metrics = self._observability.start_turn()
        ReadOnlyPolicy.validate_request({"question": question})

        environment = EnvironmentGuard.resolve(filters)
        merged_filters = EnvironmentGuard.merge_filters(filters, environment)

        cache_key = SemanticCache.make_key(
            question, session_id, environment.value, session_subject, explicit_subject
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            metrics.cache_hit = True
            ctx, response = cached
            return ctx, response
        metrics.cache_miss = True

        if session_doc:
            self._memory.load_session_context(session_doc, environment=environment)

        t0 = time.perf_counter()
        ctx = self._investigation.run(
            question=question,
            session_id=session_id,
            session_subject=session_subject,
            explicit_subject=explicit_subject,
            filters=merged_filters,
            system_prompt=system_prompt,
        )
        metrics.tool_latency_ms["investigation"] = round((time.perf_counter() - t0) * 1000, 2)

        # Evidence engine — every answer is evidence-backed.
        evidence_items = self._evidence_engine.collect(ctx, environment=environment.value)
        if evidence_items:
            ctx.evidence = [e.to_dict() for e in evidence_items]
            ctx.citations = self._evidence_engine.build_citations(evidence_items)

        # Reasoning engine — prepare analysis for LLM / structured output.
        reasoning = self._reasoning_engine.prepare(ctx, evidence=evidence_items)
        ctx.metadata["reasoning"] = reasoning

        response = StructuredResponse.from_investigation_context(ctx)
        response.metadata["environment"] = environment.value
        response.metadata["tools_available"] = self.list_tools()
        response.metadata["observability"] = metrics.to_dict()

        if ctx.model:
            metrics.provider = str(ctx.model)

        self._cache.set(
            cache_key,
            (ctx, response),
            ttl_seconds=self._config.cache_ttl,
            tags=[f"session:{session_id}", f"env:{environment.value}"],
        )
        return ctx, response

    def invalidate_session_cache(self, session_id: str) -> int:
        return self._cache.invalidate(tag=f"session:{session_id}")

    def _build_default_registry(self) -> CapabilityRegistry:
        tools = build_investigation_tools(retriever=self._config.retriever)
        return CapabilityRegistry.from_investigation_tools(tools)
