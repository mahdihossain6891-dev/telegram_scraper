"""Build bounded RAG context and assemble prompts (no Mongo / no LLM calls)."""

from __future__ import annotations

import logging
from typing import Any

from ai.prompts import PromptLoader
from ai.providers.base import ChatMessage
from ai.rag.evidence import EvidenceItem
from ai.rag.user_enrichment import (
    USER_META_KEY,
    format_sender_line,
    format_users_roster,
    unique_users_from_evidence,
)

logger = logging.getLogger("ai.rag.context_builder")

_DEFAULT_CITATION_INSTRUCTIONS = (
    "Cite evidence using the bracket labels shown in each chunk "
    "(e.g. [E1], [E2]). Only cite chunks that support the claim."
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class ContextBuilder:
    """Format evidence under char/token budgets and assemble chat messages."""

    def __init__(
        self,
        *,
        prompt_loader: PromptLoader | None = None,
        prompt_id: str = "rag_answer",
        prompt_version: str = "latest",
        max_evidence_items: int = 8,
        max_context_chars: int = 12_000,
        context_token_budget: int = 3_000,
        citation_instructions: str = _DEFAULT_CITATION_INSTRUCTIONS,
    ) -> None:
        self.prompt_loader = prompt_loader or PromptLoader()
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.max_evidence_items = max(1, int(max_evidence_items))
        self.max_context_chars = max(256, int(max_context_chars))
        self.context_token_budget = max(64, int(context_token_budget))
        self.citation_instructions = citation_instructions

    def select_evidence(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """Apply item count + character/token budgets to retrieved evidence."""
        selected: list[EvidenceItem] = []
        used_chars = 0
        used_tokens = 0
        for item in evidence[: self.max_evidence_items * 2]:
            if len(selected) >= self.max_evidence_items:
                break
            body = item.text.strip()
            if not body:
                continue
            # Leave room for labels / separators.
            overhead = 64
            piece_chars = len(body) + overhead
            piece_tokens = estimate_tokens(body) + 8
            if selected and (
                used_chars + piece_chars > self.max_context_chars
                or used_tokens + piece_tokens > self.context_token_budget
            ):
                break
            # Truncate oversized single chunk to fit remaining budget.
            remaining_chars = self.max_context_chars - used_chars - overhead
            remaining_tokens = self.context_token_budget - used_tokens - 8
            max_body_chars = min(remaining_chars, remaining_tokens * 4)
            if max_body_chars < 40:
                break
            if len(body) > max_body_chars:
                body = body[: max(0, max_body_chars - 1)].rstrip() + "…"
            selected.append(
                EvidenceItem(
                    chunk_id=item.chunk_id,
                    score=item.score,
                    text=body,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    citation_label=item.citation_label,
                    metadata=dict(item.metadata),
                    mongo_record=item.mongo_record,
                )
            )
            used_chars += len(body) + overhead
            used_tokens += estimate_tokens(body) + 8

        logger.debug(
            "rag_context_selected",
            extra={
                "ai_selected": len(selected),
                "ai_chars": used_chars,
                "ai_est_tokens": used_tokens,
            },
        )
        return selected

    def format_evidence_block(self, evidence: list[EvidenceItem]) -> str:
        """Render evidence as a labeled Markdown block for the prompt.

        Includes a Connected Users roster and per-chunk sender identity so the
        LLM never has to invent names from bare Telegram IDs.
        """
        if not evidence:
            return "(No evidence retrieved.)"

        parts: list[str] = []
        roster = format_users_roster(unique_users_from_evidence(evidence))
        if roster:
            parts.append(roster)

        for index, item in enumerate(evidence, start=1):
            label = f"E{index}"
            meta = item.metadata or {}
            user = meta.get(USER_META_KEY)
            sender_line = format_sender_line(
                user if isinstance(user, dict) else None,
                sender_id=meta.get("sender_id"),
            )
            header = (
                f"[{label}] score={item.score:.4f} "
                f"cite={item.citation_label} chunk_id={item.chunk_id}"
            )
            # Compact enriched user object for the model (not shown as raw Mongo).
            user_json = ""
            if isinstance(user, dict):
                user_json = (
                    "User: {"
                    f"user_id={user.get('user_id')!r}, "
                    f"display_name={user.get('display_name')!r}, "
                    f"first_name={user.get('first_name')!r}, "
                    f"last_name={user.get('last_name')!r}, "
                    f"username={user.get('username')!r}, "
                    f"risk_score={user.get('risk_score')!r}, "
                    f"behavior_score={user.get('behavior_score')!r}"
                    "}"
                )
            chunk_parts = [header, sender_line]
            if user_json:
                chunk_parts.append(user_json)
            chunk_parts.append(item.text)
            parts.append("\n".join(chunk_parts))
        return "\n\n".join(parts)

    def build_prompt_text(
        self,
        question: str,
        evidence: list[EvidenceItem],
    ) -> str:
        """Render the versioned ``rag_answer`` prompt with substitutions."""
        block = self.format_evidence_block(evidence)
        rendered = self.prompt_loader.render(
            self.prompt_id,
            version=self.prompt_version,
            question=question,
            evidence_chunks=block,
            citation_instructions=self.citation_instructions,
        )
        return rendered.text

    def build(
        self,
        question: str,
        evidence: list[EvidenceItem],
        *,
        system_prompt: str = "",
    ) -> list[ChatMessage]:
        """Assemble chat messages for the configured ``ChatModelProvider``."""
        selected = self.select_evidence(evidence)
        user_text = self.build_prompt_text(question, selected)
        messages: list[ChatMessage] = []
        if system_prompt.strip():
            messages.append(ChatMessage(role="system", content=system_prompt.strip()))
        messages.append(ChatMessage(role="user", content=user_text))
        return messages

    def build_from_hits(
        self,
        question: str,
        hits: list[Any],
        *,
        system_prompt: str = "",
    ) -> list[ChatMessage]:
        """Legacy helper accepting ``RetrievalHit``-like objects."""
        evidence = [
            EvidenceItem(
                chunk_id=getattr(h, "chunk_id", ""),
                score=float(getattr(h, "score", 0.0)),
                text=str(getattr(h, "text", "") or ""),
                metadata=dict(getattr(h, "metadata", {}) or {}),
                source_type=str(
                    (getattr(h, "metadata", {}) or {}).get("source_type") or "message"
                ),
                source_id=str(
                    (getattr(h, "metadata", {}) or {}).get("source_id") or ""
                ),
                citation_label=str(
                    (getattr(h, "metadata", {}) or {}).get("citation_label")
                    or getattr(h, "chunk_id", "")
                ),
            )
            for h in hits
        ]
        return self.build(question, evidence, system_prompt=system_prompt)
