"""AI NER service — LLM extraction with confidence scores."""

from __future__ import annotations

import logging
from typing import Any

from ai.extraction.models import AI_ENTITY_TYPES, AIEntityCandidate
from ai.llm.client import LLMClient
from ai.llm.json_mode import JSONModeClient
from ai.prompts import PromptLoader
from ai.providers.base import ChatMessage, ChatModelProvider
from ai.providers.errors import ProviderError

logger = logging.getLogger("ai.extraction.ner")


class NERService:
    """Extract entities from message text via the configured chat provider."""

    def __init__(
        self,
        provider: ChatModelProvider,
        *,
        model: str = "",
        prompt_loader: PromptLoader | None = None,
        prompt_id: str = "entity_extraction",
        prompt_version: str = "latest",
        max_tokens: int | None = 1024,
        min_confidence: float = 0.0,
    ) -> None:
        self.provider = provider
        self.model = model.strip()
        self.prompt_loader = prompt_loader or PromptLoader()
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version
        self.max_tokens = max_tokens
        self.min_confidence = float(min_confidence)
        self._json = JSONModeClient(
            provider,
            default_model=self.model,
            default_max_tokens=max_tokens,
            default_temperature=0.0,
        )
        # Keep LLMClient available for non-JSON fallbacks / logging parity.
        self._llm = LLMClient(
            provider,
            default_model=self.model,
            default_max_tokens=max_tokens,
            default_temperature=0.0,
        )

    def extract(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[AIEntityCandidate]:
        """Return AI entity candidates for ``text`` (does not touch Mongo)."""
        body = (text or "").strip()
        if not body:
            return []

        known = ", ".join(AI_ENTITY_TYPES)
        prompt = self.prompt_loader.render(
            self.prompt_id,
            version=self.prompt_version,
            message_text=body,
            known_entity_types=known,
        )
        messages = [ChatMessage(role="user", content=prompt.text)]

        try:
            payload = self._json.complete_json(
                messages,
                model=self.model or None,
                max_tokens=self.max_tokens,
            )
        except ProviderError:
            logger.exception("ai_entity_extraction_failed")
            raise

        raw_entities = payload.get("entities")
        if not isinstance(raw_entities, list):
            logger.warning(
                "ai_entity_payload_missing_entities",
                extra={"ai_keys": list(payload.keys())},
            )
            return []

        allowed = set(AI_ENTITY_TYPES)
        # Accept common aliases from models.
        aliases = {
            "mention": "username",
            "user": "username",
            "person_name": "person",
            "personal_name": "person",
            "name": "person",
            "org": "organization",
            "organisation": "organization",
            "company": "organization",
            "place": "location",
            "geo": "location",
            "crypto_wallet": "wallet",
            "wallet_address": "wallet",
            "telephone": "phone",
            "phone_number": "phone",
            "link": "url",
        }

        results: list[AIEntityCandidate] = []
        for row in raw_entities:
            if not isinstance(row, dict):
                continue
            etype = str(row.get("entity_type") or "").strip().lower()
            etype = aliases.get(etype, etype)
            value = str(row.get("entity_value") or row.get("value") or "").strip()
            if not etype or not value or etype not in allowed:
                continue
            try:
                confidence = float(row.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            if confidence < self.min_confidence:
                continue

            start = row.get("start_offset")
            end = row.get("end_offset")
            try:
                start_i = int(start) if start is not None else None
            except (TypeError, ValueError):
                start_i = None
            try:
                end_i = int(end) if end is not None else None
            except (TypeError, ValueError):
                end_i = None

            results.append(
                AIEntityCandidate(
                    entity_type=etype,
                    entity_value=value,
                    confidence=confidence,
                    start_offset=start_i,
                    end_offset=end_i,
                    source="ai",
                    metadata=dict(metadata or {}),
                )
            )

        logger.info(
            "ai_entities_extracted",
            extra={"ai_count": len(results), "ai_text_chars": len(body)},
        )
        return results
