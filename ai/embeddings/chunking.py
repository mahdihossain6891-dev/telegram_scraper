"""Intelligent text chunking for flagged Telegram messages."""

from __future__ import annotations

import re
from typing import Any, Iterable

from ai.embeddings.hashing import content_hash
from ai.models.schemas import AIDocumentChunk

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")


class ChunkingService:
    """Split long documents into overlapping, semantic-ish chunks."""

    def __init__(
        self,
        *,
        max_chars: int = 1200,
        overlap_chars: int = 150,
        min_chars: int = 40,
    ) -> None:
        if max_chars < 32:
            raise ValueError("max_chars must be >= 32")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be >= 0 and < max_chars")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.min_chars = min_chars

    def chunk_text(
        self,
        text: str,
        *,
        source_type: str,
        source_id: str,
        metadata: dict[str, Any] | None = None,
        embedding_model: str = "",
    ) -> list[AIDocumentChunk]:
        """Chunk a single document into ``AIDocumentChunk`` values."""
        cleaned = (text or "").strip()
        if not cleaned:
            return []

        base_meta = dict(metadata or {})
        units = self._split_units(cleaned)
        windows = self._pack_windows(units)
        chunks: list[AIDocumentChunk] = []

        for index, window in enumerate(windows):
            body = window.strip()
            if len(body) < self.min_chars and index > 0:
                # Tiny trailing fragment — merge into previous when possible.
                if chunks:
                    prev = chunks[-1]
                    merged = f"{prev.text} {body}".strip()
                    chunks[-1] = AIDocumentChunk(
                        chunk_id=prev.chunk_id,
                        source_type=prev.source_type,
                        source_id=prev.source_id,
                        text=merged,
                        metadata={
                            **prev.metadata,
                            "char_count": len(merged),
                            "content_hash": content_hash(
                                merged, embedding_model=embedding_model
                            ),
                        },
                    )
                continue

            digest = content_hash(body, embedding_model=embedding_model)
            chunk_id = f"{source_type}:{source_id}:c{index}:{digest[:12]}"
            meta = {
                **base_meta,
                "chunk_index": index,
                "char_count": len(body),
                "content_hash": digest,
            }
            chunks.append(
                AIDocumentChunk(
                    chunk_id=chunk_id,
                    source_type=source_type,
                    source_id=str(source_id),
                    text=body,
                    metadata=meta,
                )
            )
        return chunks

    def chunk_message(
        self,
        message: dict[str, Any],
        *,
        embedding_model: str = "",
    ) -> list[AIDocumentChunk]:
        """Chunk a Mongo message document (flagged / stored message)."""
        text = (message.get("text") or "").strip()
        if not text:
            return []

        row_id = message.get("_id")
        chat_id = message.get("chat_id")
        message_id = message.get("message_id")
        source_id = str(row_id if row_id is not None else f"{chat_id}:{message_id}")

        metadata = {
            "message_row_id": row_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "sender_id": message.get("sender_id"),
            "timestamp": _iso(message.get("timestamp")),
            "risk_score": message.get("risk_score"),
            "risk_level": message.get("risk_level"),
            "media_type": message.get("media_type"),
        }
        return self.chunk_text(
            text,
            source_type="message",
            source_id=source_id,
            metadata=metadata,
            embedding_model=embedding_model,
        )

    def chunk_records(
        self,
        records: Iterable[dict[str, Any]],
        *,
        embedding_model: str = "",
    ) -> list[AIDocumentChunk]:
        """Chunk an iterable of message documents."""
        out: list[AIDocumentChunk] = []
        for record in records:
            out.extend(self.chunk_message(record, embedding_model=embedding_model))
        return out

    def _split_units(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
        units: list[str] = []
        for para in paragraphs or [text]:
            if len(para) <= self.max_chars:
                units.append(para)
                continue
            sentences = [s.strip() for s in _SENTENCE_SPLIT.split(para) if s.strip()]
            if not sentences:
                units.extend(self._hard_wrap(para))
                continue
            for sentence in sentences:
                if len(sentence) <= self.max_chars:
                    units.append(sentence)
                else:
                    units.extend(self._hard_wrap(sentence))
        return units

    def _hard_wrap(self, text: str) -> list[str]:
        step = max(1, self.max_chars - self.overlap_chars)
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.max_chars)
            parts.append(text[start:end].strip())
            if end >= len(text):
                break
            start += step
        return [p for p in parts if p]

    def _pack_windows(self, units: list[str]) -> list[str]:
        if not units:
            return []
        windows: list[str] = []
        current = ""
        for unit in units:
            candidate = unit if not current else f"{current} {unit}"
            if len(candidate) <= self.max_chars:
                current = candidate
                continue
            if current:
                windows.append(current)
            if len(unit) <= self.max_chars:
                # Overlap: carry tail of previous window when helpful.
                if windows and self.overlap_chars > 0:
                    tail = windows[-1][-self.overlap_chars :].strip()
                    current = f"{tail} {unit}".strip() if tail else unit
                    if len(current) > self.max_chars:
                        current = unit
                else:
                    current = unit
            else:
                windows.extend(self._hard_wrap(unit))
                current = ""
        if current:
            windows.append(current)
        return windows


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    return str(value)
