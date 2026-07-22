"""Entity Resolution — resolve named subjects before RAG / LLM.

Pipeline position:
  Intent Detection → **Entity Resolution → Validation** → RAG → LLM

If a named entity cannot be uniquely resolved in the monitored Mongo dataset,
the assistant must not retrieve evidence or call the LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal

from ai.rag.user_enrichment import (
    UserIdentityEnricher,
    build_display_name,
    format_username,
    normalize_username,
)

logger = logging.getLogger("ai.investigation.entity_resolution")

ResolutionStatus = Literal[
    "not_required",
    "resolved",
    "no_match",
    "ambiguous",
]

EntityKind = Literal["user", "group", "channel", "chat"]

# Phrases that are not person/group names when stripping investigate prompts.
_STOP_PREFIXES = re.compile(
    r"^(?:please\s+)?(?:investigate|analyze|explain|find|lookup|look\s*up|"
    r"search|check|show|summarize|who\s+is|tell\s+me\s+about|what\s+about|"
    r"review|profile|risk\s+of|activity\s+of|behavior\s+of)\s+",
    re.I,
)
_STOP_SUFFIXES = re.compile(
    r"\s+(?:and\s+summarize.*|risk|activity|behavior|profile|timeline|"
    r"relationships?|connections?|anomalies)\s*$",
    re.I,
)
_USER_ID_RE = re.compile(
    r"\b(?:user(?:_id)?|uid|telegram\s*(?:id|user)?)\s*[:=]?\s*(-?\d+)\b",
    re.I,
)
_BARE_ID_RE = re.compile(r"(?<![\w@])(-?\d{5,})(?![\w])")
_USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,32})\b")
_QUOTED_RE = re.compile(r"[\"'“”]([^\"'“”]{2,80})[\"'“”]")
_PROPER_NAME_RE = re.compile(
    r"\b([A-Z][a-zA-Z'`-]{1,30}(?:\s+[A-Z][a-zA-Z'`-]{1,30}){0,3})\b"
)
_GROUP_HINT_RE = re.compile(
    r"\b(?:group|channel|chat|supergroup)\s+[\"']?([^\"'\n?]{2,80})",
    re.I,
)
_NAMED_RE = re.compile(
    r"\b(?:named|called|user|person|subject|suspect)\s+[\"']?"
    r"(@?[A-Za-z][\w.'-]{1,40}(?:\s+[A-Za-z][\w.'-]{1,40}){0,3})",
    re.I,
)

_GENERIC_WORDS = frozenset(
    {
        "user",
        "users",
        "group",
        "groups",
        "channel",
        "channels",
        "chat",
        "chats",
        "risk",
        "high",
        "low",
        "medium",
        "alert",
        "alerts",
        "message",
        "messages",
        "investigation",
        "summary",
        "timeline",
        "behavior",
        "behaviour",
        "behavioral",
        "behavioural",
        "anomaly",
        "anomalies",
        "activity",
        "patterns",
        "pattern",
        "report",
        "dashboard",
        "fleet",
        "overview",
        "platform",
        "module",
        "overall",
        "generate",
        "produce",
        "create",
        "write",
        "related",
        "connected",
        "matching",
        "similar",
        "evidence",
        "this",
        "that",
        "these",
        "those",
        "someone",
        "anyone",
        "everyone",
        "unknown",
        "telegram",
        "why",
        "what",
        "who",
        "how",
        "when",
        "where",
        "show",
        "list",
        "find",
        "explain",
        "analyze",
        "analyse",
        "investigate",
        "open",
        "describe",
        "please",
    }
)

# Remainder after stripping investigate/show prefixes that is still an intent phrase.
_INTENT_REMAINDER_RE = re.compile(
    r"\b(?:anomal(?:y|ies)|behaviou?r|dashboard|fleet|overview|summary|"
    r"timeline|report|alert|risk|relationship|connection|graph|"
    r"high\s+risk|this\s+user)\b",
    re.I,
)

_FUZZY_MIN = 0.72
_AMBIGUOUS_GAP = 0.08  # top scores within this gap → ambiguous
_MAX_CANDIDATES = 8


@dataclass(slots=True)
class EntityMention:
    """A raw entity mention extracted from the analyst query."""

    raw: str
    kind_hint: EntityKind | None = None
    is_username: bool = False
    is_id: bool = False


@dataclass(slots=True)
class ResolvedEntity:
    """One candidate or confirmed entity from the monitored dataset."""

    entity_type: EntityKind
    entity_id: int | str
    display_name: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    chat_type: str | None = None
    risk_score: int | None = None
    behavior_score: int | None = None
    score: float = 1.0
    match_reason: str = "exact"

    def label(self) -> str:
        handle = format_username(self.username)
        if handle and handle not in self.display_name:
            return f"{self.display_name} ({handle})"
        return self.display_name

    def to_subject(self) -> dict[str, Any]:
        if self.entity_type == "user":
            subject: dict[str, Any] = {
                "subject_type": "user",
                "subject_id": str(self.entity_id),
                "user_id": int(self.entity_id),
                "display_name": self.display_name,
            }
            if self.username:
                subject["username"] = str(self.username).lstrip("@")
            if self.first_name:
                subject["first_name"] = self.first_name
            if self.last_name:
                subject["last_name"] = self.last_name
            if self.risk_score is not None:
                subject["risk_score"] = self.risk_score
            if self.behavior_score is not None:
                subject["behavior_score"] = self.behavior_score
            return subject
        subject = {
            "subject_type": self.entity_type,
            "subject_id": str(self.entity_id),
            "chat_id": int(self.entity_id) if str(self.entity_id).lstrip("-").isdigit() else self.entity_id,
            "display_name": self.display_name,
        }
        if self.username:
            subject["username"] = str(self.username).lstrip("@")
        if self.chat_type:
            subject["chat_type"] = self.chat_type
        return subject

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "display_name": self.display_name,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "chat_type": self.chat_type,
            "risk_score": self.risk_score,
            "behavior_score": self.behavior_score,
            "score": round(float(self.score), 4),
            "match_reason": self.match_reason,
            "label": self.label(),
        }


@dataclass(slots=True)
class EntityResolutionResult:
    """Outcome of resolving entities referenced in a query."""

    status: ResolutionStatus
    query: str
    mentions: list[EntityMention] = field(default_factory=list)
    resolved: list[ResolvedEntity] = field(default_factory=list)
    candidates: list[ResolvedEntity] = field(default_factory=list)
    unmatched_query: str | None = None
    message: str = ""
    suggestions: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: str = "high"

    @property
    def primary(self) -> ResolvedEntity | None:
        return self.resolved[0] if self.resolved else None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "entity_resolution": {
                "status": self.status,
                "query": self.query,
                "unmatched_query": self.unmatched_query,
                "message": self.message,
                "suggestions": list(self.suggestions),
                "reason": self.reason,
                "confidence": self.confidence,
                "mentions": [m.raw for m in self.mentions],
                "resolved": [e.to_dict() for e in self.resolved],
                "candidates": [e.to_dict() for e in self.candidates],
            }
        }

    def format_answer(self) -> str:
        if self.status == "no_match":
            target = self.unmatched_query or "the requested entity"
            lines = [
                "Status: No Match Found",
                "",
                f'Message: "No monitored user, group, or channel matching \'{target}\' was found."',
                "",
                "Suggestions:",
                "- Check spelling",
                "- Search by username",
                "- Search by Telegram ID",
                "",
                "Confidence: 100%",
                "",
                "Reason: Entity does not exist in the monitored dataset.",
            ]
            return "\n".join(lines)

        if self.status == "ambiguous":
            lines = [
                "Status: Ambiguous Match",
                "",
                "Did you mean:",
                "",
            ]
            for cand in self.candidates[:_MAX_CANDIDATES]:
                lines.append(f"• {cand.label()}")
            lines.extend(
                [
                    "",
                    "Select one entity from the matching results to continue the investigation.",
                    "",
                    "Confidence: 100%",
                    "",
                    "Reason: Multiple monitored entities match this query.",
                ]
            )
            return "\n".join(lines)

        return self.message


def extract_entity_mentions(question: str) -> list[EntityMention]:
    """Extract candidate entity mentions from an analyst question."""
    text = (question or "").strip()
    if not text:
        return []

    mentions: list[EntityMention] = []
    seen: set[str] = set()

    def add(raw: str, **kwargs: Any) -> None:
        cleaned = (raw or "").strip(" \t\n\r.,;:!?")
        if len(cleaned) < 2:
            return
        key = cleaned.lower()
        if key in seen or key in _GENERIC_WORDS:
            return
        # Skip if every token is generic.
        tokens = [t for t in re.split(r"\s+", key) if t]
        if tokens and all(t in _GENERIC_WORDS for t in tokens):
            return
        seen.add(key)
        mentions.append(EntityMention(raw=cleaned, **kwargs))

    for m in _USERNAME_RE.finditer(text):
        add(m.group(1), is_username=True, kind_hint="user")

    for m in _USER_ID_RE.finditer(text):
        add(m.group(1), is_id=True, kind_hint="user")

    for m in _QUOTED_RE.finditer(text):
        add(m.group(1))

    for m in _GROUP_HINT_RE.finditer(text):
        add(m.group(1), kind_hint="group")

    for m in _NAMED_RE.finditer(text):
        add(m.group(1))

    # Investigate / analyze <name>
    stripped = _STOP_PREFIXES.sub("", text)
    stripped = _STOP_SUFFIXES.sub("", stripped).strip(" ?")
    if stripped and stripped.lower() != text.lower():
        # Prefer the remainder as a name when it looks like an entity.
        if _USERNAME_RE.fullmatch(stripped) or stripped.lstrip("-").isdigit():
            pass
        elif (
            len(stripped.split()) <= 5
            and not stripped.lower().startswith(
                ("why ", "what ", "how ", "show ", "list ", "generate ", "find related")
            )
            and not _INTENT_REMAINDER_RE.search(stripped)
        ):
            add(stripped)
            # Also capture proper-case spans inside the stripped subject.
            for m in _PROPER_NAME_RE.finditer(stripped):
                add(m.group(1).strip())

    # Bare numeric Telegram IDs when clearly present.
    if not any(m.is_id for m in mentions):
        for m in _BARE_ID_RE.finditer(text):
            add(m.group(1), is_id=True, kind_hint="user")

    # Whole-query entity lookups (incl. lowercase names like "adib malay").
    if not mentions:
        from ai.investigation.intents import _looks_like_entity_query

        if _looks_like_entity_query(text):
            cleaned = text.strip().rstrip("?.!")
            if cleaned.lstrip("-").isdigit():
                add(cleaned, is_id=True, kind_hint="user")
            elif cleaned.startswith("@"):
                add(cleaned.lstrip("@"), is_username=True, kind_hint="user")
            else:
                add(cleaned, kind_hint="user")

    return mentions


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class EntityResolver:
    """Resolve mentions against monitored Mongo collections (read-only)."""

    def __init__(self, db: Any = None) -> None:
        self.db = db
        self.identity = UserIdentityEnricher(db)

    def resolve_query(
        self,
        question: str,
        *,
        existing_subject: dict[str, Any] | None = None,
        explicit_subject: dict[str, Any] | None = None,
    ) -> EntityResolutionResult:
        """Resolve entities for a turn.

        - Explicit numeric subject from the API is preferred when present.
        - Mentions in the question are validated against Mongo.
        - Mentions with no match → ``no_match`` (block RAG/LLM).
        - Multiple close matches → ``ambiguous`` (block RAG/LLM).
        - No mentions and no subject → ``not_required`` (general RAG allowed).
        """
        q = (question or "").strip()
        existing_subject = dict(existing_subject or {})
        explicit_subject = dict(explicit_subject or {})

        # Explicit subject from UI (e.g. numeric user filter) must exist.
        if explicit_subject.get("user_id") is not None:
            return self._resolve_explicit_user(q, int(explicit_subject["user_id"]))
        if explicit_subject.get("chat_id") is not None:
            return self._resolve_explicit_chat(q, int(explicit_subject["chat_id"]))

        mentions = extract_entity_mentions(q)

        # Follow-up turns: session already has a resolved subject and no new mention.
        if not mentions and existing_subject.get("user_id") is not None:
            return self._resolve_explicit_user(q, int(existing_subject["user_id"]))
        if not mentions and existing_subject.get("chat_id") is not None:
            return self._resolve_explicit_chat(q, int(existing_subject["chat_id"]))

        if not mentions:
            return EntityResolutionResult(
                status="not_required",
                query=q,
                reason="No named entity detected; general evidence retrieval allowed.",
                confidence="high",
            )

        # Resolve the strongest / first substantive mention.
        primary = mentions[0]
        for mention in mentions:
            if mention.is_id or mention.is_username or " " in mention.raw:
                primary = mention
                break

        return self.resolve_mention(primary, query=q, all_mentions=mentions)

    def resolve_mention(
        self,
        mention: EntityMention,
        *,
        query: str = "",
        all_mentions: list[EntityMention] | None = None,
    ) -> EntityResolutionResult:
        # Search → dedupe by Telegram ID → decide unique vs ambiguous.
        candidates = dedupe_entities(self.search(mention))
        if not candidates:
            return EntityResolutionResult(
                status="no_match",
                query=query,
                mentions=all_mentions or [mention],
                unmatched_query=mention.raw,
                message=(
                    f"No monitored user, group, or channel matching "
                    f"'{mention.raw}' was found."
                ),
                suggestions=[
                    "Check spelling",
                    "Search by username",
                    "Search by Telegram ID",
                ],
                reason="Entity does not exist in the monitored dataset.",
                confidence="high",
            )

        top = candidates[0]
        close = dedupe_entities(
            [
                c
                for c in candidates
                if abs(c.score - top.score) <= _AMBIGUOUS_GAP and c.score >= _FUZZY_MIN
            ]
        )
        # Exact ID / exact username → always unique if present.
        if mention.is_id or (mention.is_username and top.match_reason.startswith("exact")):
            close = [top]
        elif top.match_reason.startswith("exact") and top.score >= 0.99:
            exact_peers = dedupe_entities(
                [c for c in candidates if c.match_reason.startswith("exact")]
            )
            close = exact_peers if len(exact_peers) > 1 else [top]

        # One unique Telegram identity → auto-resolve (never ask the analyst).
        if len(close) <= 1:
            chosen = close[0] if close else top
            return EntityResolutionResult(
                status="resolved",
                query=query,
                mentions=all_mentions or [mention],
                resolved=[chosen],
                message=f"Resolved entity: {chosen.label()}",
                reason="Entity uniquely matched in the monitored dataset.",
                confidence="high",
            )

        return EntityResolutionResult(
            status="ambiguous",
            query=query,
            mentions=all_mentions or [mention],
            candidates=close[:_MAX_CANDIDATES],
            unmatched_query=mention.raw,
            message="Multiple monitored entities match this query.",
            suggestions=[
                "Select one entity from the matching results",
                "Search by username",
                "Search by Telegram ID",
            ],
            reason="Multiple monitored entities match this query.",
            confidence="high",
        )

    def search(self, mention: EntityMention) -> list[ResolvedEntity]:
        """Search users + chats with exact then fuzzy matching."""
        if self.db is None:
            return []

        raw = mention.raw.strip()
        results: list[ResolvedEntity] = []

        if mention.is_id or raw.lstrip("-").isdigit():
            try:
                uid = int(raw)
            except ValueError:
                uid = None
            if uid is not None:
                user = self._user_by_id(uid)
                if user:
                    return [user]
                chat = self._chat_by_id(uid)
                if chat:
                    return [chat]
                return []

        if mention.is_username or raw.startswith("@"):
            handle = normalize_username(raw)
            if handle:
                results.extend(self._users_by_username(handle, exact=True))
                results.extend(self._chats_by_username(handle, exact=True))
                if results:
                    return dedupe_entities(results)

        # Name / title search (exact-ish then fuzzy).
        results.extend(self._users_by_name(raw))
        if mention.kind_hint in {None, "group", "channel", "chat"}:
            results.extend(self._chats_by_title(raw))

        return dedupe_entities(results)

    def _resolve_explicit_user(self, query: str, user_id: int) -> EntityResolutionResult:
        user = self._user_by_id(user_id)
        if not user:
            return EntityResolutionResult(
                status="no_match",
                query=query,
                unmatched_query=str(user_id),
                message=(
                    f"No monitored user, group, or channel matching "
                    f"'{user_id}' was found."
                ),
                suggestions=[
                    "Check spelling",
                    "Search by username",
                    "Search by Telegram ID",
                ],
                reason="Entity does not exist in the monitored dataset.",
                confidence="high",
            )
        return EntityResolutionResult(
            status="resolved",
            query=query,
            resolved=[user],
            message=f"Resolved entity: {user.label()}",
            reason="Entity uniquely matched in the monitored dataset.",
            confidence="high",
        )

    def _resolve_explicit_chat(self, query: str, chat_id: int) -> EntityResolutionResult:
        chat = self._chat_by_id(chat_id)
        if not chat:
            return EntityResolutionResult(
                status="no_match",
                query=query,
                unmatched_query=str(chat_id),
                message=(
                    f"No monitored user, group, or channel matching "
                    f"'{chat_id}' was found."
                ),
                suggestions=[
                    "Check spelling",
                    "Search by username",
                    "Search by Telegram ID",
                ],
                reason="Entity does not exist in the monitored dataset.",
                confidence="high",
            )
        return EntityResolutionResult(
            status="resolved",
            query=query,
            resolved=[chat],
            message=f"Resolved entity: {chat.label()}",
            reason="Entity uniquely matched in the monitored dataset.",
            confidence="high",
        )

    def _user_by_id(self, user_id: int) -> ResolvedEntity | None:
        enriched = self.identity.lookup_one(user_id)
        if not enriched:
            return None
        # Confirm the user exists in monitored data (users or user_activity).
        exists = False
        if self.db is not None:
            exists = bool(
                self.db["users"].find_one({"_id": user_id}, {"_id": 1})
                or self.db["user_activity"].find_one({"_id": user_id}, {"_id": 1})
            )
        if not exists and enriched.get("display_name", "").startswith("Unknown User"):
            return None
        if not exists:
            # lookup_one synthesizes Unknown User when missing — treat as no match.
            if not (
                enriched.get("username")
                or enriched.get("first_name")
                or enriched.get("last_name")
            ):
                return None
        return ResolvedEntity(
            entity_type="user",
            entity_id=user_id,
            display_name=str(enriched.get("display_name") or f"User {user_id}"),
            username=enriched.get("username"),
            first_name=enriched.get("first_name"),
            last_name=enriched.get("last_name"),
            risk_score=enriched.get("risk_score"),
            behavior_score=enriched.get("behavior_score"),
            score=1.0,
            match_reason="exact_id",
        )

    def _chat_by_id(self, chat_id: int) -> ResolvedEntity | None:
        if self.db is None:
            return None
        doc = self.db["chats"].find_one({"_id": chat_id})
        if not doc:
            return None
        return _chat_entity(doc, score=1.0, reason="exact_id")

    def _users_by_username(self, handle: str, *, exact: bool) -> list[ResolvedEntity]:
        if self.db is None:
            return []
        rx = re.compile(f"^{re.escape(handle)}$", re.I) if exact else re.compile(
            re.escape(handle), re.I
        )
        out: list[ResolvedEntity] = []
        seen: set[int] = set()
        for coll in ("users", "user_activity"):
            for doc in self.db[coll].find({"username": rx}).limit(20):
                try:
                    uid = int(doc["_id"])
                except (TypeError, ValueError):
                    continue
                if uid in seen:
                    continue
                seen.add(uid)
                enriched = self.identity.lookup_one(uid) or {}
                out.append(
                    ResolvedEntity(
                        entity_type="user",
                        entity_id=uid,
                        display_name=str(
                            enriched.get("display_name")
                            or build_display_name(
                                first_name=doc.get("first_name"),
                                last_name=doc.get("last_name"),
                                username=doc.get("username"),
                                user_id=uid,
                            )
                        ),
                        username=format_username(
                            enriched.get("username") or doc.get("username")
                        ),
                        first_name=enriched.get("first_name") or doc.get("first_name"),
                        last_name=enriched.get("last_name") or doc.get("last_name"),
                        risk_score=enriched.get("risk_score") or doc.get("risk_score"),
                        behavior_score=enriched.get("behavior_score"),
                        score=1.0 if exact else _similarity(handle, str(doc.get("username") or "")),
                        match_reason="exact_username" if exact else "fuzzy_username",
                    )
                )
        return dedupe_entities(out)

    def _chats_by_username(self, handle: str, *, exact: bool) -> list[ResolvedEntity]:
        if self.db is None:
            return []
        rx = re.compile(f"^{re.escape(handle)}$", re.I) if exact else re.compile(
            re.escape(handle), re.I
        )
        out: list[ResolvedEntity] = []
        for doc in self.db["chats"].find({"username": rx}).limit(20):
            out.append(
                _chat_entity(
                    doc,
                    score=1.0 if exact else _similarity(handle, str(doc.get("username") or "")),
                    reason="exact_username" if exact else "fuzzy_username",
                )
            )
        return dedupe_entities(out)

    def _users_by_name(self, name: str) -> list[ResolvedEntity]:
        if self.db is None:
            return []
        tokens = [t for t in re.split(r"\s+", name.strip()) if t]
        if not tokens:
            return []

        # Build a Mongo filter that requires each token to appear in name fields.
        token_clauses = []
        for tok in tokens[:4]:
            rx = re.compile(re.escape(tok), re.I)
            token_clauses.append(
                {
                    "$or": [
                        {"first_name": rx},
                        {"last_name": rx},
                        {"username": rx},
                        {"display_name": rx},
                    ]
                }
            )
        query = {"$and": token_clauses} if len(token_clauses) > 1 else token_clauses[0]

        scored: list[ResolvedEntity] = []
        seen: set[int] = set()
        for coll in ("user_activity", "users"):
            try:
                cursor = self.db[coll].find(query).limit(40)
            except Exception:  # noqa: BLE001
                continue
            for doc in cursor:
                try:
                    uid = int(doc["_id"])
                except (TypeError, ValueError):
                    continue
                if uid in seen:
                    continue
                seen.add(uid)
                enriched = self.identity.lookup_one(uid) or {}
                display = str(
                    enriched.get("display_name")
                    or build_display_name(
                        display_name=doc.get("display_name"),
                        first_name=doc.get("first_name") or enriched.get("first_name"),
                        last_name=doc.get("last_name") or enriched.get("last_name"),
                        username=doc.get("username") or enriched.get("username"),
                        user_id=uid,
                    )
                )
                full = " ".join(
                    p
                    for p in (
                        doc.get("first_name") or enriched.get("first_name"),
                        doc.get("last_name") or enriched.get("last_name"),
                    )
                    if p
                )
                score = max(
                    _similarity(name, display),
                    _similarity(name, full) if full else 0.0,
                    _similarity(name, str(doc.get("username") or "")),
                )
                # Exact full-name match boost.
                if full and full.lower() == name.lower():
                    score = 1.0
                    reason = "exact_name"
                elif display.lower() == name.lower():
                    score = 1.0
                    reason = "exact_name"
                elif score >= 0.92:
                    reason = "near_exact_name"
                else:
                    reason = "fuzzy_name"
                if score < _FUZZY_MIN:
                    continue
                scored.append(
                    ResolvedEntity(
                        entity_type="user",
                        entity_id=uid,
                        display_name=display,
                        username=format_username(
                            enriched.get("username") or doc.get("username")
                        ),
                        first_name=enriched.get("first_name") or doc.get("first_name"),
                        last_name=enriched.get("last_name") or doc.get("last_name"),
                        risk_score=enriched.get("risk_score") or doc.get("risk_score"),
                        behavior_score=enriched.get("behavior_score"),
                        score=score,
                        match_reason=reason,
                    )
                )
        return dedupe_entities(scored)

    def _chats_by_title(self, title: str) -> list[ResolvedEntity]:
        if self.db is None:
            return []
        tokens = [t for t in re.split(r"\s+", title.strip()) if t]
        if not tokens:
            return []
        token_clauses = []
        for tok in tokens[:4]:
            rx = re.compile(re.escape(tok), re.I)
            token_clauses.append({"$or": [{"title": rx}, {"username": rx}]})
        query = {"$and": token_clauses} if len(token_clauses) > 1 else token_clauses[0]
        out: list[ResolvedEntity] = []
        try:
            cursor = self.db["chats"].find(query).limit(40)
        except Exception:  # noqa: BLE001
            return []
        for doc in cursor:
            label = str(doc.get("title") or doc.get("username") or doc.get("_id"))
            score = max(
                _similarity(title, label),
                _similarity(title, str(doc.get("username") or "")),
            )
            if str(doc.get("title") or "").lower() == title.lower():
                score = 1.0
                reason = "exact_title"
            elif score >= 0.92:
                reason = "near_exact_title"
            else:
                reason = "fuzzy_title"
            if score < _FUZZY_MIN:
                continue
            out.append(_chat_entity(doc, score=score, reason=reason))
        return dedupe_entities(out)


def _chat_entity(doc: dict[str, Any], *, score: float, reason: str) -> ResolvedEntity:
    raw_id = doc.get("_id")
    try:
        chat_id: int | str = int(raw_id) if raw_id is not None else ""
    except (TypeError, ValueError):
        chat_id = str(raw_id) if raw_id is not None else ""
    chat_type = str(doc.get("chat_type") or "").lower()
    if "channel" in chat_type:
        etype: EntityKind = "channel"
    elif "group" in chat_type or "supergroup" in chat_type:
        etype = "group"
    else:
        etype = "chat"
    title = doc.get("title") or format_username(doc.get("username")) or f"Chat {chat_id}"
    return ResolvedEntity(
        entity_type=etype,
        entity_id=chat_id,
        display_name=str(title),
        username=format_username(doc.get("username")),
        chat_type=doc.get("chat_type"),
        score=score,
        match_reason=reason,
    )


def _normalize_entity_id(entity_id: int | str) -> int | str:
    """Normalize Telegram IDs so ``123`` and ``\"123\"`` collapse to one key."""
    if isinstance(entity_id, bool):
        return entity_id
    if isinstance(entity_id, int):
        return entity_id
    text = str(entity_id).strip()
    if not text:
        return text
    try:
        return int(text)
    except ValueError:
        return text


def _entity_dedupe_key(item: ResolvedEntity) -> tuple[str, str]:
    """Primary uniqueness key: Telegram ID (+ user vs chat namespace).

    Group/channel/chat kinds share the same Telegram chat ID space, so they
    collapse together. Users stay in a separate namespace.
    """
    eid = str(_normalize_entity_id(item.entity_id))
    if item.entity_type == "user":
        return ("user", eid)
    return ("chat", eid)


def _merge_entities(primary: ResolvedEntity, secondary: ResolvedEntity) -> ResolvedEntity:
    """Keep the stronger match and fill missing metadata from the other record."""
    if secondary.score > primary.score:
        primary, secondary = secondary, primary
    return ResolvedEntity(
        entity_type=primary.entity_type,
        entity_id=_normalize_entity_id(primary.entity_id),
        display_name=primary.display_name or secondary.display_name,
        username=primary.username or secondary.username,
        first_name=primary.first_name or secondary.first_name,
        last_name=primary.last_name or secondary.last_name,
        chat_type=primary.chat_type or secondary.chat_type,
        risk_score=(
            primary.risk_score
            if primary.risk_score is not None
            else secondary.risk_score
        ),
        behavior_score=(
            primary.behavior_score
            if primary.behavior_score is not None
            else secondary.behavior_score
        ),
        score=max(primary.score, secondary.score),
        match_reason=primary.match_reason or secondary.match_reason,
    )


def dedupe_entities(items: list[ResolvedEntity]) -> list[ResolvedEntity]:
    """Collapse search hits that refer to the same Telegram identity.

    Telegram User/Chat ID is the primary unique key. Duplicate rows from
    ``users`` + ``user_activity`` (or int/str ID variants) become one entity.
    """
    best: dict[tuple[str, str], ResolvedEntity] = {}
    for item in items:
        normalized = ResolvedEntity(
            entity_type=item.entity_type,
            entity_id=_normalize_entity_id(item.entity_id),
            display_name=item.display_name,
            username=item.username,
            first_name=item.first_name,
            last_name=item.last_name,
            chat_type=item.chat_type,
            risk_score=item.risk_score,
            behavior_score=item.behavior_score,
            score=item.score,
            match_reason=item.match_reason,
        )
        key = _entity_dedupe_key(normalized)
        prev = best.get(key)
        best[key] = normalized if prev is None else _merge_entities(prev, normalized)
    return sorted(best.values(), key=lambda e: (-e.score, e.label().lower()))


# Backwards-compatible alias.
_dedupe_sorted = dedupe_entities
