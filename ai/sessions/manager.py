"""Investigation session manager — wraps SessionStore with Phase 8 model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai.core.types import PlatformEnvironment
from ai.investigation.session_store import SessionStore
from ai.sessions.models import InvestigationSession


class InvestigationSessionManager:
    """Manages multiple simultaneous investigations."""

    def __init__(self, store: SessionStore | None = None, *, db: Any = None) -> None:
        self._store = store or SessionStore(db)

    @property
    def store(self) -> SessionStore:
        return self._store

    def create(
        self,
        *,
        session_id: str | None = None,
        subject: dict[str, Any] | None = None,
        environment: PlatformEnvironment = PlatformEnvironment.LIVE,
    ) -> InvestigationSession:
        doc = self._store.get_or_create(session_id, subject=subject)
        return self._from_doc(doc, environment=environment)

    def get(self, session_id: str, *, environment: PlatformEnvironment = PlatformEnvironment.LIVE) -> InvestigationSession | None:
        doc = self._store.get(session_id)
        if not doc:
            return None
        return self._from_doc(doc, environment=environment)

    def dismiss(self, session_id: str) -> None:
        self._store.dismiss(session_id)

    def append_turn(self, session_id: str, *, role: str, content: str, **meta: Any) -> None:
        self._store.append_turn(session_id, role=role, content=content, **meta)

    def update_subject(self, session_id: str, subject: dict[str, Any]) -> None:
        self._store.update_subject(session_id, subject)

    def _from_doc(self, doc: dict[str, Any], *, environment: PlatformEnvironment) -> InvestigationSession:
        messages = list(doc.get("messages") or [])
        return InvestigationSession(
            session_id=str(doc.get("_id") or ""),
            target=dict(doc.get("subject") or {}),
            environment=environment.value,
            history=messages,
            conversation=messages,
            created_at=doc.get("created_at") or datetime.now(timezone.utc),
            metadata={"status": doc.get("status")},
        )
