"""LLM explanation step — explain InvestigationContext only, never invent evidence."""

from __future__ import annotations

import json
import logging
from typing import Any

from ai.investigation.context import InvestigationContext
from ai.investigation.threat_analysis import format_threat_report_markdown
from ai.investigation.tools import DEFAULT_TOOL_POLICY
from ai.models.schemas import Citation
from ai.providers.base import ChatMessage
from ai.rag.response_parser import parse_rag_completion

logger = logging.getLogger("ai.investigation.explain")

_EXPLAIN_INSTRUCTIONS = """
You are a senior SOC analyst writing an enterprise threat intelligence report.

Rules:
- Use ONLY the InvestigationContext JSON, threat_report, and Evidence list below.
- Do NOT invent users, alerts, relationships, scores, or messages.
- Never classify a subject as dangerous based on keywords alone.
- Separate keyword detection from operational intent. Explain uncertainty.
- Prefer "insufficient evidence" over incorrect accusations.
- If a field is missing, state that evidence was not available.
- Cite evidence using [E#] labels only when referencing specific messages.

Structure the answer EXACTLY with these markdown headings:

# Investigation Report

## Executive Summary
Analyst-grade summary: overall assessment, why detection fired, whether activity
appears malicious, suspicious, informational, or unknown.

## Subject Information
Identity, Telegram ID, username, messages analyzed, groups/channels, first/last seen.

## Risk Assessment
Include Detection, Behavior, Network, and Intent scores, false positive adjustment,
final score (0-100), risk band (LOW/MEDIUM/HIGH/CRITICAL), and score explanation.

## Evidence Analysis
Message-by-message: timestamp, chat, sender, intent classification, confidence, reason.

## Behavioral Analysis
Posting patterns, volume, alerts, coordination indicators.

## Network Analysis
Shared groups, relationship edges, suspicious connections.

## False Positive Assessment
Whether keyword-only, reference content, or actual suspicious communication.

## Threat Classification
Per-category breakdown with intent and confidence.

## Analyst Recommendation
Priority (Low/Medium/High/Critical), recommended action, escalation triggers.

## Confidence Level
Score and reason for assessment confidence.

Use threat_report as the authoritative structured analysis. Expand with evidence
snippets where helpful. Do not contradict threat_report scores.
""".strip()


def build_explanation_messages(
    ctx: InvestigationContext,
    *,
    system_prompt: str,
    evidence_package: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    grounding = evidence_package or ctx.to_grounding_dict()
    if ctx.threat_report and "threat_report" not in grounding:
        grounding = {**grounding, "threat_report": ctx.threat_report}
    evidence_items = list(
        (evidence_package or {}).get("evidence") or ctx.evidence or []
    )[:12]
    evidence_lines = []
    for item in evidence_items:
        label = item.get("label") or "[E?]"
        ts = item.get("timestamp") or "unknown time"
        snippet = (item.get("snippet") or item.get("text") or "").strip()
        evidence_lines.append(f"{label} ({ts}): {snippet}")

    user_content = (
        f"Analyst question:\n{ctx.question}\n\n"
        f"{_EXPLAIN_INSTRUCTIONS}\n\n"
        f"InvestigationContext (authoritative — produced by Investigation Planner "
        f"+ Tool Registry + Threat Analysis, not by the model):\n"
        f"{json.dumps(grounding, ensure_ascii=False, default=str, indent=2)}\n\n"
        f"Evidence snippets:\n"
        + ("\n".join(evidence_lines) if evidence_lines else "(no evidence snippets)")
    )
    return [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_content),
    ]


def explain_investigation(
    ctx: InvestigationContext,
    *,
    llm: Any,
    system_prompt: str,
    evidence_package: dict[str, Any] | None = None,
) -> InvestigationContext:
    """Call the LLM to explain findings. Does not retrieve new evidence."""
    if not ctx.evidence and not ctx.findings:
        ctx.status = "no_evidence"
        ctx.refused = True
        ctx.answer = (
            "No supporting evidence found.\n\n"
            "Structured investigation tools did not return enough monitored "
            "evidence to produce a grounded explanation."
        )
        return ctx

    messages = build_explanation_messages(
        ctx,
        system_prompt=system_prompt,
        evidence_package=evidence_package,
    )
    completion = llm.complete(messages)
    raw = (completion.content or "").strip()
    # parse_rag_completion expects evidence items for citation binding; we pass [].
    parsed = parse_rag_completion(raw, [])

    answer = (parsed.answer or raw or "").strip()
    if not answer or answer == "No answer generated.":
        answer = raw
    if not answer:
        ctx.status = "no_evidence"
        ctx.refused = True
        ctx.answer = "No supporting evidence found."
        ctx.model = getattr(completion, "model", "") or ""
        return ctx

    # Ensure confidence block present.
    conf = ctx.threat_report.get("confidence_level") if ctx.threat_report else None
    if conf and "confidence level" not in answer.lower():
        answer = (
            f"{answer.rstrip()}\n\n"
            f"## Confidence Level\n"
            f"{conf.get('score_pct')}% ({conf.get('label')}) — {conf.get('reason')}"
        )
    elif ctx.confidence and "confidence" not in answer.lower():
        answer = (
            f"{answer.rstrip()}\n\n"
            f"Confidence: {ctx.confidence.score}% ({ctx.confidence.label})\n"
            f"Reason: {ctx.confidence.reason}"
        )

    if ctx.next_actions and "recommendation" not in answer.lower():
        rec = (ctx.threat_report or {}).get("analyst_recommendation") or {}
        if rec.get("recommended_action"):
            lines = [
                "\n## Analyst Recommendation",
                f"Priority: {rec.get('priority')}",
                f"Action: {rec.get('recommended_action')}",
            ]
            answer = answer.rstrip() + "\n" + "\n".join(lines)

    ctx.answer = answer
    ctx.model = getattr(completion, "model", "") or ""
    ctx.status = "explained"
    ctx.refused = False
    ctx.metadata["tool_policy"] = DEFAULT_TOOL_POLICY
    return ctx


def citations_from_context(ctx: InvestigationContext) -> list[Citation]:
    out: list[Citation] = []
    for c in ctx.citations:
        out.append(
            Citation(
                source_type=str(c.get("source_type") or "message"),
                source_id=str(c.get("source_id") or ""),
                label=str(c.get("label") or ""),
                snippet=str(c.get("snippet") or "")[:240],
            )
        )
    return out
