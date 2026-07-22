"""InvestigationOrchestrator — Sébastien's enterprise investigation pipeline.

Pipeline:
  Intent → Validate → Resolve Entities → Investigation Planner →
  Tool Registry → Evidence Validation → Context Builder → LLM Explain

The LLM never decides how to retrieve information. The planner does.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ai.investigation.confidence import assess_confidence
from ai.investigation.context import InvestigationContext, ToolExecution
from ai.investigation.context_builder import InvestigationContextBuilder
from ai.investigation.engine import run_investigation_engine
from ai.investigation.entity_resolution import EntityResolver
from ai.investigation.evidence_validation import validate_investigation_evidence
from ai.investigation.explain import explain_investigation
from ai.investigation.intents import (
    InvestigationIntent,
    build_retrieval_question,
    classify_intent,
)
from ai.investigation.threat_analysis import ThreatReport, format_threat_report_markdown
from ai.investigation.next_actions import recommend_next_actions
from ai.investigation.planner import (
    InvestigationPlanner,
    PlanExecutor,
    WorkflowTrace,
    get_planner_memory,
)
from ai.investigation.planner.models import PlanStep
from ai.investigation.tools import (
    DEFAULT_TOOL_POLICY,
    ToolRegistry,
    default_tool_registry,
    enrich_subject_identity,
    extract_subject_hints,
)
from ai.investigation.validators import extract_alert_id, validate_intent_inputs
from ai.tools.registry import CapabilityRegistry

logger = logging.getLogger("ai.investigation.orchestrator")


def _is_concrete_entity_miss(resolution: Any) -> bool:
    """True when no_match refers to a real @handle / Telegram ID / proper name."""
    mentions = list(getattr(resolution, "mentions", None) or [])
    if any(getattr(m, "is_id", False) or getattr(m, "is_username", False) for m in mentions):
        return True
    raw = str(
        getattr(resolution, "unmatched_query", None)
        or (mentions[0].raw if mentions else "")
        or ""
    ).strip()
    if not raw:
        return False
    # Soft / prompt-like leftovers should not hard-fail.
    if len(raw.split()) >= 5:
        return False
    lower = raw.lower()
    soft_bits = (
        "risk",
        "anomal",
        "behav",
        "dashboard",
        "fleet",
        "overview",
        "summary",
        "this user",
        "high risk",
        "why ",
        "what ",
        "show ",
        "analyze ",
        "investigate ",
    )
    if any(bit in lower for bit in soft_bits):
        return False
    # Short proper names / bare handles without @ still count as concrete.
    return bool(raw) and not raw.lower().startswith(("why", "what", "how", "show"))


@dataclass(slots=True)
class OrchestratorDeps:
    db: Any = None
    retriever: Any = None
    llm: Any = None
    entity_resolver: EntityResolver | None = None
    tools: ToolRegistry | None = None
    top_k: int = 8
    planner: InvestigationPlanner | None = None
    deselected_tools: list[str] | None = None


class InvestigationOrchestrator:
    """Coordinates planner + tools; LLM only explains InvestigationContext."""

    def __init__(self, deps: OrchestratorDeps) -> None:
        self.deps = deps
        self.entity_resolver = deps.entity_resolver or EntityResolver(deps.db)
        self.tools = deps.tools or default_tool_registry(retriever=deps.retriever)
        caps = CapabilityRegistry.from_investigation_tools(self.tools)
        self.planner = deps.planner or InvestigationPlanner(caps)
        self.executor = PlanExecutor(self.tools, memory=get_planner_memory())
        self.context_builder = InvestigationContextBuilder()

    def run(
        self,
        *,
        question: str,
        session_id: str,
        session_subject: dict[str, Any] | None = None,
        explicit_subject: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        system_prompt: str = "",
        deselected_tools: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> InvestigationContext:
        wall_start = time.perf_counter()
        q = (question or "").strip()
        ctx = InvestigationContext(question=q, session_id=session_id)
        ctx.db = self.deps.db  # type: ignore[attr-defined]
        ctx.retriever = self.deps.retriever  # type: ignore[attr-defined]
        ctx.filters = dict(filters or {})  # type: ignore[attr-defined]
        ctx.top_k = self.deps.top_k  # type: ignore[attr-defined]

        workflow = WorkflowTrace(user_query=q, stages=["user_query"])

        if not q:
            ctx.status = "validation_failed"
            ctx.refused = True
            ctx.validation_message = "Question is empty."
            ctx.answer = "Question is empty."
            return ctx

        intent = classify_intent(q)
        ctx.intent_key = intent.key
        ctx.intent_label = intent.label
        ctx.status = "intent_detected"
        workflow.detected_intent = intent.key
        workflow.intent_label = intent.label
        workflow.stages.append("detected_intent")

        if intent.key == "unknown" or (intent.block_llm and intent.key == "unknown"):
            return self._fail(
                ctx,
                status="unknown_intent",
                answer=(
                    "I could not determine a clear investigation intent.\n\n"
                    "Sébastien is an investigation copilot — not a general chatbot.\n"
                    "Please choose an investigation type (Investigate User, Analyze "
                    "Behavior, Explain Alert, Generate Timeline, etc.) and provide "
                    "a monitored target."
                ),
                suggestions=[
                    "Investigate a user by @username or Telegram ID",
                    "Analyze behavior for a resolved user",
                    "Explain an alert by ID",
                ],
            )

        session_subject = dict(session_subject or {})
        explicit = dict(explicit_subject or {})
        hints = extract_subject_hints(q)
        explicit.update({k: v for k, v in hints.items() if v is not None})
        alert_id = extract_alert_id(q)
        if alert_id:
            explicit.setdefault("alert_id", alert_id)

        resolution = self.entity_resolver.resolve_query(
            q,
            existing_subject=session_subject,
            explicit_subject=explicit or None,
        )
        needs_target = bool(set(intent.requires) - {"none"})

        # Suggested prompts often leave soft/false mentions ("Why is this user…").
        # Only hard-fail no_match when the mention looks like a concrete target.
        if resolution.status == "no_match":
            if not needs_target or not _is_concrete_entity_miss(resolution):
                from ai.investigation.entity_resolution import EntityResolutionResult

                resolution = EntityResolutionResult(
                    status="not_required",
                    query=q,
                    reason=(
                        "No concrete entity mention to resolve; "
                        "continue with intent validation."
                    ),
                    confidence="high",
                )
            else:
                ctx.entity_resolution = resolution.to_metadata().get(
                    "entity_resolution", {}
                )
                return self._fail(
                    ctx,
                    status="entity_missing",
                    answer=resolution.format_answer(),
                    suggestions=list(resolution.suggestions),
                    entity_meta=resolution.to_metadata(),
                )

        ctx.entity_resolution = resolution.to_metadata().get("entity_resolution", {})

        if resolution.status == "ambiguous":
            ctx.status = "entity_ambiguous"
            ctx.refused = True
            ctx.answer = resolution.format_answer()
            ctx.validation_suggestions = list(resolution.suggestions)
            ctx.metadata.update(resolution.to_metadata())
            return ctx

        subject = dict(session_subject)
        if explicit:
            subject.update({k: v for k, v in explicit.items() if v is not None})
        if resolution.status == "resolved" and resolution.primary:
            subject.update(resolution.primary.to_subject())
        subject = enrich_subject_identity(subject, db=self.deps.db)
        ctx.subject = subject
        get_planner_memory().remember_target(session_id, subject)

        validation = validate_intent_inputs(
            intent,
            question=q,
            subject=subject,
            entity_status=resolution.status,
        )
        has_target = ctx.has_target()
        if needs_target and not has_target:
            return self._fail(
                ctx,
                status="target_required",
                answer=(
                    "No investigation target selected.\n\n"
                    "Please search for and select a monitored user before starting "
                    "an investigation."
                ),
                suggestions=[
                    "Enter a username, display name, or Telegram ID",
                    "Select an entity from matching results",
                ],
            )
        if not validation.ok and needs_target:
            return self._fail(
                ctx,
                status="validation_failed",
                answer=validation.message,
                suggestions=validation.suggestions,
            )

        if intent.key == "open_dashboard_page":
            return self._dashboard_only(ctx, intent)

        plan_start = time.perf_counter()
        skip = list(deselected_tools or self.deps.deselected_tools or [])
        plan = self.planner.plan(
            intent,
            question=q,
            target=subject,
            deselected_tools=skip,
            available_tools=self.tools.list_tools(),
        )
        tool_names = [s.tool for s in plan.active_steps()]
        if "search" not in tool_names and not intent.block_llm:
            plan.steps.append(
                PlanStep(
                    tool="search",
                    order=len(plan.steps) + 1,
                    priority="required",
                    mode="sequential",
                    reason="Collect message evidence for grounded explanation.",
                    estimated_ms=400,
                    evidence_needed=["message_evidence", "citations"],
                )
            )
            if "search" not in plan.required_tools:
                plan.required_tools.append("search")
        ctx.tools_requested = [s.tool for s in plan.active_steps()]
        workflow.plan = plan.to_dict()
        workflow.planning_ms = round((time.perf_counter() - plan_start) * 1000, 2)
        workflow.stages.append("execution_plan")
        ctx.metadata["execution_plan"] = plan.to_dict()

        retrieval_question = build_retrieval_question(q, intent, subject=subject)
        results, records = self.executor.execute(
            plan,
            ctx=ctx,
            retrieval_question=retrieval_question,
        )
        by_name = {r.tool: r for r in records}
        enriched: list[ToolExecution] = []
        for ex in results:
            rec = by_name.get(ex.name)
            if rec:
                enriched.append(
                    ToolExecution(
                        name=ex.name,
                        ok=ex.ok,
                        summary=ex.summary,
                        data=ex.data,
                        error=ex.error,
                        latency_ms=rec.latency_ms,
                        cached=rec.cached,
                        confidence=rec.confidence,
                        freshness=rec.freshness,
                        completeness=rec.completeness,
                        impact=rec.impact,
                    )
                )
            else:
                enriched.append(ex)
        ctx.question = q
        ctx.tool_results = enriched
        workflow.tools_executed = [r.to_dict() for r in records]
        workflow.total_tool_ms = round(sum(r.latency_ms for r in records), 2)
        workflow.stages.append("tools_executed")

        failed = [r for r in records if not r.ok]
        if failed:
            ctx.metadata["tool_failures"] = [
                {"tool": r.tool, "reason": r.error, "impact": r.impact}
                for r in failed
            ]

        ctx = run_investigation_engine(ctx)
        workflow.stages.append("evidence_retrieved")

        if not ctx.evidence and not ctx.findings:
            workflow.stages.append("aborted_no_evidence")
            ctx.metadata["workflow"] = workflow.to_dict()
            return self._fail(
                ctx,
                status="no_evidence",
                answer=(
                    "No supporting evidence found.\n\n"
                    "No monitored evidence or structured analytics were available "
                    "for this target."
                ),
                suggestions=[
                    "Confirm the subject is monitored",
                    "Try a different username or Telegram ID",
                    "Open Personnel Activity for this user",
                ],
            )

        if not ctx.evidence and ctx.findings:
            ctx.metadata["evidence_limited"] = True

        validation_report = validate_investigation_evidence(ctx)
        workflow.validation = validation_report
        workflow.stages.append("evidence_validated")
        ctx = self.context_builder.apply_to_context(ctx)
        built = self.context_builder.build(ctx)
        workflow.evidence_count = built["evidence_count"]
        workflow.context_chars = built["context_chars"]
        workflow.stages.append("context_built")

        get_planner_memory().pin_evidence(
            session_id,
            [e for e in ctx.evidence if float(e.get("confidence") or 0) >= 0.7][:8],
        )

        ctx.confidence = assess_confidence(ctx)
        ctx.next_actions = recommend_next_actions(ctx)
        ctx.status = "ready_for_explain"

        if intent.block_llm:
            ctx.answer = self._format_structured_answer(ctx)
            ctx.refused = False
            ctx.status = "explained"
            workflow.response_generated = True
            workflow.stages.extend(["response_generated"])
            workflow.total_ms = round((time.perf_counter() - wall_start) * 1000, 2)
            ctx.metadata["workflow"] = workflow.to_dict()
            return ctx

        if self.deps.llm is None:
            ctx.answer = self._format_structured_answer(ctx)
            ctx.status = "explained"
            workflow.response_generated = True
            workflow.stages.append("response_generated")
            workflow.total_ms = round((time.perf_counter() - wall_start) * 1000, 2)
            ctx.metadata["workflow"] = workflow.to_dict()
            return ctx

        llm = self.deps.llm
        if provider or model or temperature is not None or max_tokens is not None:
            from ai.llm.client import create_llm_client
            from ai.config import get_ai_settings

            llm = create_llm_client(
                get_ai_settings(),
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        explain_start = time.perf_counter()
        ctx = explain_investigation(
            ctx,
            llm=llm,
            system_prompt=system_prompt
            or (
                "You are Sébastien, an AI Investigation Copilot. "
                f"{DEFAULT_TOOL_POLICY}"
            ),
            evidence_package=built["package"],
        )
        workflow.explain_ms = round((time.perf_counter() - explain_start) * 1000, 2)
        workflow.model_used = ctx.model or ""
        workflow.prompt_chars = int(
            (ctx.metadata.get("context_builder") or {}).get("context_chars") or 0
        )
        workflow.response_generated = bool(ctx.answer) and not ctx.refused
        workflow.stages.extend(["model_used", "response_generated"])
        workflow.total_ms = round((time.perf_counter() - wall_start) * 1000, 2)
        ctx.metadata["workflow"] = workflow.to_dict()
        ctx.metadata["observability"] = {
            "planning_ms": workflow.planning_ms,
            "tool_latency_ms": workflow.total_tool_ms,
            "tool_failures": len(failed),
            "evidence_count": workflow.evidence_count,
            "context_size": workflow.context_chars,
            "prompt_size": workflow.prompt_chars,
            "response_time_ms": workflow.total_ms,
        }
        return ctx

    def _dashboard_only(
        self, ctx: InvestigationContext, intent: InvestigationIntent
    ) -> InvestigationContext:
        result = self.tools.run("dashboard", ctx=ctx)
        ctx.tool_results = [
            ToolExecution(
                name=result.name,
                ok=result.ok,
                summary=result.summary,
                data=dict(result.data or {}),
                error=result.error,
            )
        ]
        ctx = run_investigation_engine(ctx)
        matched = (result.data or {}).get("matched") or []
        if matched:
            lines = ["Open these dashboard modules (do not invent data in chat):", ""]
            for m in matched:
                lines.append(f"- {m.get('label')}: {m.get('path')}")
            ctx.answer = "\n".join(lines)
        else:
            mods = (result.data or {}).get("modules") or []
            lines = [
                "Sébastien can orchestrate these dashboard modules:",
                "",
            ]
            for m in mods:
                lines.append(f"- {m.get('label')}: {m.get('path')}")
            lines.append("")
            lines.append("Specify which page to open (e.g. “Open Behavior Analytics”).")
            ctx.answer = "\n".join(lines)
        ctx.next_actions = recommend_next_actions(ctx)
        ctx.confidence = assess_confidence(ctx)
        ctx.status = "explained"
        ctx.refused = False
        ctx.intent_key = intent.key
        ctx.intent_label = intent.label
        ctx.metadata["workflow"] = WorkflowTrace(
            user_query=ctx.question,
            detected_intent=intent.key,
            intent_label=intent.label,
            tools_executed=[{"tool": "dashboard", "ok": result.ok}],
            response_generated=True,
            stages=[
                "user_query",
                "detected_intent",
                "tools_executed",
                "response_generated",
            ],
        ).to_dict()
        return ctx

    def _fail(
        self,
        ctx: InvestigationContext,
        *,
        status: str,
        answer: str,
        suggestions: list[str] | None = None,
        entity_meta: dict[str, Any] | None = None,
    ) -> InvestigationContext:
        ctx.status = status  # type: ignore[assignment]
        ctx.refused = True
        ctx.answer = answer
        ctx.validation_message = answer
        ctx.validation_suggestions = list(suggestions or [])
        if entity_meta:
            ctx.metadata.update(entity_meta)
        if status in {"entity_missing", "target_required", "validation_failed"}:
            ctx.entity_resolution = {
                **dict(ctx.entity_resolution or {}),
                "status": (
                    "no_match"
                    if status == "entity_missing"
                    else "target_required"
                    if status == "target_required"
                    else "validation_failed"
                ),
                "suggestions": list(suggestions or []),
                "message": answer.split("\n", 1)[0],
            }
        return ctx

    def _format_structured_answer(self, ctx: InvestigationContext) -> str:
        if ctx.threat_report:
            try:
                report = ThreatReport(**{
                    k: v for k, v in ctx.threat_report.items()
                    if k in ThreatReport.__dataclass_fields__
                })
                return format_threat_report_markdown(report)
            except (TypeError, ValueError):
                pass
        lines = [
            f"Investigation: {ctx.intent_label}",
            "",
        ]
        if ctx.subject:
            name = (
                ctx.subject.get("display_name")
                or ctx.subject.get("username")
                or ctx.subject.get("user_id")
                or ctx.subject.get("chat_id")
            )
            lines.append(f"Target: {name}")
            lines.append("")
        if ctx.findings:
            lines.append("Key Findings:")
            for f in ctx.findings:
                lines.append(f"- {f.title}: {f.summary}")
            lines.append("")
        if ctx.confidence:
            lines.append(
                f"Confidence: {ctx.confidence.score}% ({ctx.confidence.label})"
            )
            lines.append(f"Reason: {ctx.confidence.reason}")
            lines.append("")
        if ctx.next_actions:
            lines.append("Recommended Next Actions:")
            for a in ctx.next_actions:
                lines.append(f"- {a.label}: {a.reason}")
        if not ctx.findings:
            lines.append("No supporting evidence found.")
        return "\n".join(lines).strip()
