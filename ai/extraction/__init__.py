"""Supplemental AI entity extraction.

Does **not** replace ``entity_extractor.py``. Regex entities in
``extracted_entities`` are never overwritten. AI results live in ``ai_entities``.
"""

from __future__ import annotations

from .merge import EntityMergeService
from .models import AI_ENTITY_TYPES, AIEntityCandidate, AIEntityRecord
from .ner_service import NERService
from .normalize import normalize_entity_value
from .repository import AIEntityRepository
from .service import EntityExtractionService

__all__ = [
    "AI_ENTITY_TYPES",
    "AIEntityCandidate",
    "AIEntityRecord",
    "AIEntityRepository",
    "EntityExtractionService",
    "EntityMergeService",
    "NERService",
    "normalize_entity_value",
]
