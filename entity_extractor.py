"""Regex-based entity extraction from message text."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import Settings, ensure_directories, load_settings
from database import get_session, init_db
from models import ExtractedEntity, Message
from utils import get_logger

logger = get_logger("entity_extractor")

CONTENT_ENTITY_TYPES: frozenset[str] = frozenset(
    {"url", "domain", "email", "phone", "mention", "hashtag"}
)
KEYWORD_ENTITY_TYPES: frozenset[str] = frozenset(
    {"narcotics", "human_trafficking", "firearms"}
)


@dataclass(frozen=True)
class EntityMatch:
    """An entity found in message text."""

    entity_type: str
    entity_value: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class ExtractionResult:
    """Summary of an entity extraction run."""

    messages_processed: int
    entities_stored: int
    entities_skipped: int


class BaseEntityExtractor(ABC):
    """Base class for pluggable entity extractors."""

    entity_type: ClassVar[str]

    @abstractmethod
    def extract(self, text: str) -> list[EntityMatch]:
        """Return all matches found in ``text``."""


class UrlExtractor(BaseEntityExtractor):
    entity_type = "url"
    _pattern = re.compile(r"""https?://[^\s<>"'\]]+""", re.IGNORECASE)

    def extract(self, text: str) -> list[EntityMatch]:
        return [
            EntityMatch(self.entity_type, match.group(0), match.start(), match.end())
            for match in self._pattern.finditer(text)
        ]


class EmailExtractor(BaseEntityExtractor):
    entity_type = "email"
    _pattern = re.compile(
        r"""\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b""",
    )

    def extract(self, text: str) -> list[EntityMatch]:
        return [
            EntityMatch(self.entity_type, match.group(0), match.start(), match.end())
            for match in self._pattern.finditer(text)
        ]


class HashtagExtractor(BaseEntityExtractor):
    entity_type = "hashtag"
    _pattern = re.compile(r"""(?<!\w)#[A-Za-z0-9_]+\b""")

    def extract(self, text: str) -> list[EntityMatch]:
        return [
            EntityMatch(self.entity_type, match.group(0), match.start(), match.end())
            for match in self._pattern.finditer(text)
        ]


class MentionExtractor(BaseEntityExtractor):
    entity_type = "mention"
    _pattern = re.compile(r"""(?<!\w)@[A-Za-z0-9_]+\b""")

    def extract(self, text: str) -> list[EntityMatch]:
        return [
            EntityMatch(self.entity_type, match.group(0), match.start(), match.end())
            for match in self._pattern.finditer(text)
        ]


class PhoneExtractor(BaseEntityExtractor):
    entity_type = "phone"
    _pattern = re.compile(r"""\+?\d[\d\s\-()]{7,14}\d""")

    def extract(self, text: str) -> list[EntityMatch]:
        matches: list[EntityMatch] = []
        for match in self._pattern.finditer(text):
            value = re.sub(r"\s+", " ", match.group(0).strip())
            matches.append(
                EntityMatch(self.entity_type, value, match.start(), match.end())
            )
        return matches


class DomainExtractor(BaseEntityExtractor):
    entity_type = "domain"
    _pattern = re.compile(
        r"""\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b""",
        re.IGNORECASE,
    )

    def extract(self, text: str) -> list[EntityMatch]:
        matches: list[EntityMatch] = []
        seen: set[str] = set()

        for match in UrlExtractor().extract(text):
            parsed = urlparse(match.entity_value)
            domain = parsed.netloc.lower().removeprefix("www.")
            if domain and domain not in seen:
                seen.add(domain)
                matches.append(
                    EntityMatch(self.entity_type, domain, match.start_offset, match.end_offset)
                )

        for match in self._pattern.finditer(text):
            domain = match.group(0).lower()
            if "@" in domain:
                continue
            if domain not in seen:
                seen.add(domain)
                matches.append(
                    EntityMatch(self.entity_type, domain, match.start(), match.end())
                )

        return matches


DEFAULT_EXTRACTORS: tuple[BaseEntityExtractor, ...] = (
    UrlExtractor(),
    EmailExtractor(),
    HashtagExtractor(),
    MentionExtractor(),
    PhoneExtractor(),
    DomainExtractor(),
)


def extract_entities(
    text: str | None,
    extractors: tuple[BaseEntityExtractor, ...] | None = None,
) -> list[EntityMatch]:
    """Run all configured extractors and return deduplicated matches."""
    if not text or not text.strip():
        return []

    active = extractors or DEFAULT_EXTRACTORS
    seen: set[tuple[str, str]] = set()
    results: list[EntityMatch] = []

    for extractor in active:
        for match in extractor.extract(text):
            key = (match.entity_type, match.entity_value.lower())
            if key in seen:
                continue
            seen.add(key)
            results.append(match)

    return results


def entity_already_stored(
    session: Session,
    message_row_id: int,
    entity_type: str,
    entity_value: str,
) -> bool:
    """Return True if the entity is already linked to the message."""
    stmt = select(ExtractedEntity.id).where(
        ExtractedEntity.message_row_id == message_row_id,
        ExtractedEntity.entity_type == entity_type,
        ExtractedEntity.entity_value == entity_value,
    )
    return session.scalar(stmt) is not None


def store_entities_for_message(
    session: Session,
    message_row_id: int,
    text: str | None,
    extractors: tuple[BaseEntityExtractor, ...] | None = None,
) -> tuple[int, int]:
    """Extract and store content entities for one message."""
    stored = 0
    skipped = 0

    for match in extract_entities(text, extractors=extractors):
        if entity_already_stored(session, message_row_id, match.entity_type, match.entity_value):
            skipped += 1
            continue

        session.add(
            ExtractedEntity(
                message_row_id=message_row_id,
                entity_type=match.entity_type,
                entity_value=match.entity_value,
                start_offset=match.start_offset,
                end_offset=match.end_offset,
            )
        )
        stored += 1

    if stored:
        session.flush()
        logger.debug(
            "Stored %d content entities for message_row_id=%s",
            stored,
            message_row_id,
        )

    return stored, skipped


def extract_for_all_messages(settings: Settings | None = None) -> ExtractionResult:
    """Extract content entities for all stored messages."""
    cfg = ensure_directories(settings)
    init_db(cfg)

    messages_processed = 0
    entities_stored = 0
    entities_skipped = 0

    with get_session(cfg) as session:
        messages = session.scalars(select(Message).order_by(Message.id)).all()
        for message in messages:
            stored, skipped = store_entities_for_message(
                session,
                message.id,
                message.text,
            )
            messages_processed += 1
            entities_stored += stored
            entities_skipped += skipped

    logger.info(
        "Entity extraction complete: messages=%d stored=%d skipped=%d",
        messages_processed,
        entities_stored,
        entities_skipped,
    )
    return ExtractionResult(
        messages_processed=messages_processed,
        entities_stored=entities_stored,
        entities_skipped=entities_skipped,
    )


def main() -> None:
    """CLI entry point for batch entity extraction."""
    from utils import setup_logging

    cfg = ensure_directories()
    setup_logging(cfg)

    result = extract_for_all_messages(cfg)
    print(
        "Entity extraction complete\n"
        f"  Messages processed: {result.messages_processed}\n"
        f"  Entities stored:    {result.entities_stored}\n"
        f"  Entities skipped:   {result.entities_skipped}"
    )


if __name__ == "__main__":
    main()
