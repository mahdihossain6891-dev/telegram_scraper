"""Database context — isolated storage namespace per environment.

Purpose:
    Hide whether isolation uses separate Mongo databases or collection prefixes.

Responsibilities:
    Expose database name, collection names, and namespace metadata.

Future extension:
    Inject a real ``MongoClient`` factory without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.constants import COLLECTION_STRATEGY_SEPARATE_DATABASE, KNOWN_COLLECTIONS
from simulator.enums import EnvironmentType


@dataclass(frozen=True, slots=True)
class DatabaseContext:
    """Describes the active Mongo namespace for one environment."""

    environment: EnvironmentType
    database_name: str
    collection_strategy: str = COLLECTION_STRATEGY_SEPARATE_DATABASE
    collection_prefix: str = ""
    strict_isolation: bool = True
    # Connection URI is metadata-only in Phase 2 — no live connections opened.
    connection_uri: str | None = None
    known_collections: tuple[str, ...] = field(default_factory=lambda: KNOWN_COLLECTIONS)

    def collection_name(self, logical_name: str) -> str:
        """Map a logical collection to its physical name in this environment."""
        base = logical_name.strip()
        if self.collection_strategy == COLLECTION_STRATEGY_SEPARATE_DATABASE:
            return base
        return f"{self.collection_prefix}{base}" if self.collection_prefix else base

    def collections(self) -> dict[str, str]:
        """Return logical → physical collection mapping."""
        return {name: self.collection_name(name) for name in self.known_collections}

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.value,
            "database_name": self.database_name,
            "collection_strategy": self.collection_strategy,
            "collection_prefix": self.collection_prefix,
            "strict_isolation": self.strict_isolation,
            "collections": self.collections(),
        }
