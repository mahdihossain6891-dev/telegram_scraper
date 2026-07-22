"""RAG engine — retrieve, ground, generate (no frontend dependency)."""

from __future__ import annotations

from .context_builder import ContextBuilder, estimate_tokens
from .evidence import EvidenceItem
from .mongo_loader import MongoEvidenceLoader
from .pipeline import RAGPipeline
from .response_parser import ParsedRAGOutput, heuristic_confidence, parse_rag_completion
from .retriever import Retriever
from .user_enrichment import (
    UserIdentityEnricher,
    build_display_name,
    enrich_user_record,
    format_user_bullet,
)

__all__ = [
    "ContextBuilder",
    "EvidenceItem",
    "MongoEvidenceLoader",
    "ParsedRAGOutput",
    "RAGPipeline",
    "Retriever",
    "UserIdentityEnricher",
    "build_display_name",
    "enrich_user_record",
    "estimate_tokens",
    "format_user_bullet",
    "heuristic_confidence",
    "parse_rag_completion",
]
