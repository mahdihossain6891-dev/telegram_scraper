"""Merge AI entities with regex entities without overwriting core storage.

Writes never target ``extracted_entities``. Overlaps are flagged
``matched_regex=True`` and still stored only in ``ai_entities``.
"""

from __future__ import annotations

import logging
from typing import Any

from ai.extraction.models import AIEntityCandidate
from ai.extraction.normalize import normalize_entity_value

logger = logging.getLogger("ai.extraction.merge")

# Map AI types onto regex entity_type names used in extracted_entities.
_REGEX_TYPE_ALIASES: dict[str, set[str]] = {
    "phone": {"phone"},
    "email": {"email"},
    "url": {"url"},
    "username": {"mention", "username"},
    "wallet": {"wallet"},
    "organization": {"organization"},
    "location": {"location"},
    "person": {"person"},
}


class EntityMergeService:
    """Mark AI candidates that overlap regex hits; never mutate regex rows."""

    def merge(
        self,
        regex_entities: list[dict[str, Any]],
        ai_entities: list[AIEntityCandidate] | list[dict[str, Any]],
    ) -> list[AIEntityCandidate]:
        """Return AI candidates annotated with ``matched_regex`` when overlapping.

        Args:
            regex_entities: Existing rows from ``extracted_entities`` (read-only).
            ai_entities: Fresh AI candidates (dicts or ``AIEntityCandidate``).
        """
        regex_keys = self._regex_key_set(regex_entities)
        merged: list[AIEntityCandidate] = []
        seen: set[tuple[str, str]] = set()

        for raw in ai_entities:
            candidate = (
                raw
                if isinstance(raw, AIEntityCandidate)
                else AIEntityCandidate(
                    entity_type=str(raw.get("entity_type") or ""),
                    entity_value=str(raw.get("entity_value") or raw.get("value") or ""),
                    confidence=float(raw.get("confidence") or 0.0),
                    start_offset=raw.get("start_offset"),
                    end_offset=raw.get("end_offset"),
                    matched_regex=bool(raw.get("matched_regex")),
                    source=str(raw.get("source") or "ai"),
                    metadata=dict(raw.get("metadata") or {}),
                )
            )
            if not candidate.entity_type or not candidate.entity_value:
                continue

            norm = normalize_entity_value(
                candidate.entity_type, candidate.entity_value
            )
            dedupe_key = (candidate.entity_type, norm)
            if not norm or dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            matched = False
            for regex_type in _REGEX_TYPE_ALIASES.get(
                candidate.entity_type, {candidate.entity_type}
            ):
                if (regex_type, norm) in regex_keys:
                    matched = True
                    break
                # Also compare against raw regex values normalized under AI type.
                if (candidate.entity_type, norm) in regex_keys:
                    matched = True
                    break

            merged.append(
                AIEntityCandidate(
                    entity_type=candidate.entity_type,
                    entity_value=candidate.entity_value,
                    confidence=candidate.confidence,
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                    matched_regex=matched,
                    source=candidate.source,
                    metadata={
                        **candidate.metadata,
                        "normalized_value": norm,
                        # Explicit: core regex store is never written by this path.
                        "core_entities_untouched": True,
                    },
                )
            )

        logger.debug(
            "ai_entity_merge",
            extra={
                "ai_in": len(ai_entities),
                "ai_out": len(merged),
                "ai_matched_regex": sum(1 for m in merged if m.matched_regex),
            },
        )
        return merged

    def _regex_key_set(
        self, regex_entities: list[dict[str, Any]]
    ) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for row in regex_entities:
            etype = str(row.get("entity_type") or "").strip().lower()
            value = str(row.get("entity_value") or "").strip()
            if not etype or not value:
                continue
            # Index under the regex type and under normalized AI-comparable forms.
            keys.add((etype, normalize_entity_value(etype, value)))
            if etype == "mention":
                keys.add(("username", normalize_entity_value("username", value)))
        return keys
