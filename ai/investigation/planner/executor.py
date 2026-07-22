"""Plan executor — runs ExecutionPlan steps via ToolRegistry.

Supports sequential and parallel groups. Soft-fails per tool.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from ai.investigation.context import InvestigationContext, ToolExecution
from ai.investigation.planner.models import ExecutionPlan, PlanStep, ToolRunRecord
from ai.investigation.planner.session_memory import (
    CachedToolResult,
    PlannerSessionMemory,
    get_planner_memory,
)
from ai.investigation.tools.base import ToolRegistry, ToolResult


def _tool_confidence(result: ToolResult) -> tuple[float | None, float | None, float | None]:
    data = result.data or {}
    conf = data.get("confidence")
    fresh = data.get("freshness")
    complete = data.get("completeness")
    if conf is None and result.ok:
        conf = 0.75 if result.summary else 0.55
    if fresh is None and result.ok:
        fresh = 0.8
    if complete is None and result.ok:
        complete = 0.7 if data else 0.4
    return (
        float(conf) if isinstance(conf, (int, float)) else None,
        float(fresh) if isinstance(fresh, (int, float)) else None,
        float(complete) if isinstance(complete, (int, float)) else None,
    )


class PlanExecutor:
    """Execute a plan through the Tool Registry — never via the LLM."""

    def __init__(
        self,
        tools: ToolRegistry,
        *,
        memory: PlannerSessionMemory | None = None,
        max_workers: int = 4,
    ) -> None:
        self.tools = tools
        self.memory = memory or get_planner_memory()
        self.max_workers = max(1, int(max_workers))

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        ctx: InvestigationContext,
        retrieval_question: str,
        use_cache: bool = True,
        cancel_check: Callable[[], bool] | None = None,
    ) -> tuple[list[ToolExecution], list[ToolRunRecord]]:
        steps = plan.active_steps()
        executions: list[ToolExecution] = []
        records: list[ToolRunRecord] = []

        # Group parallel steps, keep sequential order for the rest.
        parallel = [s for s in steps if s.mode == "parallel" and s.parallel_group is not None]
        sequential = [s for s in steps if s not in parallel]

        # Run parallel analytics first (except search which stays sequential last).
        if parallel and not (cancel_check and cancel_check()):
            group_exec, group_rec = self._run_parallel(
                parallel,
                ctx=ctx,
                retrieval_question=retrieval_question,
                use_cache=use_cache,
                session_id=ctx.session_id,
                target=plan.target or ctx.subject,
            )
            executions.extend(group_exec)
            records.extend(group_rec)

        for step in sequential:
            if cancel_check and cancel_check():
                break
            ex, rec = self._run_one(
                step,
                ctx=ctx,
                retrieval_question=retrieval_question,
                use_cache=use_cache,
                session_id=ctx.session_id,
                target=plan.target or ctx.subject,
            )
            executions.append(ex)
            records.append(rec)

        return executions, records

    def _run_parallel(
        self,
        steps: list[PlanStep],
        *,
        ctx: InvestigationContext,
        retrieval_question: str,
        use_cache: bool,
        session_id: str,
        target: dict[str, Any],
    ) -> tuple[list[ToolExecution], list[ToolRunRecord]]:
        executions: list[ToolExecution] = []
        records: list[ToolRunRecord] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(steps))) as pool:
            futures = {
                pool.submit(
                    self._run_one,
                    step,
                    ctx=ctx,
                    retrieval_question=retrieval_question,
                    use_cache=use_cache,
                    session_id=session_id,
                    target=target,
                ): step
                for step in steps
            }
            for fut in as_completed(futures):
                ex, rec = fut.result()
                executions.append(ex)
                records.append(rec)
        # Stable order by plan order.
        order = {s.tool: s.order for s in steps}
        executions.sort(key=lambda e: order.get(e.name, 999))
        records.sort(key=lambda r: order.get(r.tool, 999))
        return executions, records

    def _run_one(
        self,
        step: PlanStep,
        *,
        ctx: InvestigationContext,
        retrieval_question: str,
        use_cache: bool,
        session_id: str,
        target: dict[str, Any],
    ) -> tuple[ToolExecution, ToolRunRecord]:
        cache_key = self.memory.make_key(
            session_id,
            step.tool,
            target,
            question_hint=retrieval_question if step.tool == "search" else "",
        )
        if use_cache:
            cached = self.memory.get(cache_key)
            if cached is not None:
                ex = ToolExecution(
                    name=cached.tool,
                    ok=cached.ok,
                    summary=cached.summary + " (cached)",
                    data=dict(cached.data),
                    error=cached.error,
                )
                rec = ToolRunRecord(
                    tool=cached.tool,
                    ok=cached.ok,
                    latency_ms=0.0,
                    summary=ex.summary,
                    error=cached.error,
                    cached=True,
                    confidence=cached.confidence,
                    freshness=cached.freshness,
                    completeness=cached.completeness,
                    impact="" if cached.ok else "Used stale/failed cache entry",
                    data_preview=_preview(cached.data),
                )
                return ex, rec

        started = time.perf_counter()
        prev_q = ctx.question
        try:
            if step.tool == "search":
                ctx.question = retrieval_question
            result = self.tools.run(step.tool, ctx=ctx, question=retrieval_question)
        finally:
            ctx.question = prev_q

        latency = round((time.perf_counter() - started) * 1000, 2)
        conf, fresh, complete = _tool_confidence(result)
        self.memory.put(
            CachedToolResult(
                tool=step.tool,
                cache_key=cache_key,
                summary=result.summary,
                data=dict(result.data or {}),
                ok=result.ok,
                error=result.error,
                confidence=conf,
                freshness=fresh,
                completeness=complete,
            )
        )
        ex = ToolExecution(
            name=result.name,
            ok=result.ok,
            summary=result.summary,
            data=dict(result.data or {}),
            error=result.error,
        )
        impact = ""
        if not result.ok:
            impact = (
                f"{step.tool} failed — continuing with remaining evidence. "
                f"Reason: {result.error or 'unknown'}"
            )
        rec = ToolRunRecord(
            tool=step.tool,
            ok=result.ok,
            latency_ms=latency,
            summary=result.summary,
            error=result.error,
            cached=False,
            confidence=conf,
            freshness=fresh,
            completeness=complete,
            impact=impact,
            data_preview=_preview(result.data or {}),
        )
        return ex, rec


def _preview(data: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(data.items()):
        if i >= limit:
            out["…"] = f"{len(data) - limit} more keys"
            break
        if isinstance(v, list):
            out[k] = f"list[{len(v)}]"
        elif isinstance(v, dict):
            out[k] = f"object[{len(v)} keys]"
        elif isinstance(v, str) and len(v) > 120:
            out[k] = v[:120] + "…"
        else:
            out[k] = v
    return out
