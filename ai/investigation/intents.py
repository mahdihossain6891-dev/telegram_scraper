"""Intent detection for Sébastien — investigation copilot, not a chatbot.

Unknown intents must never reach the LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InvestigationIntent:
    """Detected analyst intent for an assistant turn."""

    key: str
    label: str
    retrieval_hint: str = ""
    """Tools to run after entity resolution (deterministic plan)."""
    tools: tuple[str, ...] = ()
    """Required input kinds: user | chat | alert | case | dual_user | none."""
    requires: tuple[str, ...] = ()
    """If True, never call the LLM for this intent."""
    block_llm: bool = False


# Canonical intents (ordered by specificity — first match wins).
_PATTERNS: tuple[tuple[InvestigationIntent, re.Pattern[str]], ...] = (
    (
        InvestigationIntent(
            key="compare_two_users",
            label="Compare Two Users",
            retrieval_hint="compare users risk behavior activity differences",
            tools=("risk", "behavior", "personnel", "relationship", "search"),
            requires=("dual_user",),
        ),
        re.compile(
            r"\bcompar(e|ison)\b.{0,40}\b(user|person|account|profile)s?\b|"
            r"\b(user|person).{0,20}\bvs\.?\b.{0,20}\b(user|person)",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="open_dashboard_page",
            label="Open Dashboard Page",
            tools=("dashboard",),
            requires=("none",),
            block_llm=True,
        ),
        re.compile(
            r"\b(open|go\s+to|navigate|show)\b.{0,30}\b(dashboard|page|module|"
            r"personnel|threat\s*feed|relationship\s*graph|alerts?)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="dashboard_summary",
            label="Dashboard Summary",
            retrieval_hint="overview fleet risk alerts behavioral outliers",
            tools=("dashboard", "behavior", "risk"),
            requires=("none",),
        ),
        re.compile(
            r"\b(dashboard\s+summary|fleet\s+overview|platform\s+overview|"
            r"overall\s+(risk|threat)|summary\s+of\s+(the\s+)?dashboard)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="explain_alert",
            label="Explain Alert",
            retrieval_hint="alert trigger severity supporting evidence",
            tools=("alerts", "behavior", "risk", "search"),
            requires=("alert",),
        ),
        re.compile(
            r"\b(explain|what\s+triggered|why).{0,30}\balert\b|"
            r"\balert\s+(id|#)\s*\d+\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="generate_report",
            label="Generate Report",
            retrieval_hint="investigation report executive summary citations",
            tools=("report", "risk", "behavior", "personnel"),
            requires=("user",),
        ),
        re.compile(
            r"\b(generate|produce|create|write)\b.{0,30}\b(report|brief|"
            r"intelligence\s+summary|case\s+summary)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="generate_timeline",
            label="Generate Timeline",
            retrieval_hint="timeline chronology sequence of events first seen last seen",
            tools=("timeline", "personnel", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(timeline|chronolog|sequence\s+of\s+events|over\s+time)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="analyze_behavior",
            label="Analyze Behavior",
            retrieval_hint=(
                "behavioral anomalies spike night activity forwarding "
                "media deletion language switch"
            ),
            tools=("behavior", "alerts", "risk", "timeline", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b("
            r"behaviou?ral\s+anomal|"
            r"analyze\s+behaviou?r|"
            r"behaviou?ral\s+activ|"
            r"anomal(?:y|ies)|"
            r"outlier|spike|"
            r"night\s+activ|"
            r"forward(?:ing)?\s+rate|"
            r"unusual\s+behaviou?r"
            r")\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="relationship_analysis",
            label="Relationship Analysis",
            retrieval_hint="relationship connection link between users chats forwards",
            tools=("relationship", "personnel", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(relationship|connection|link|linked|connected|associate|"
            r"related\s+users?|graph)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="investigate_channel",
            label="Investigate Channel",
            retrieval_hint="channel activity risk messages members",
            tools=("personnel", "risk", "timeline", "search"),
            requires=("chat",),
        ),
        re.compile(
            r"\b(investigate|analyze|profile)\b.{0,40}\bchannel\b|"
            r"\bchannel\b.{0,40}\b(investigate|risk|activity)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="investigate_group",
            label="Investigate Group",
            retrieval_hint="group activity risk messages members",
            tools=("personnel", "risk", "timeline", "search"),
            requires=("chat",),
        ),
        re.compile(
            r"\b(investigate|analyze|profile)\b.{0,40}\b(group|supergroup)\b|"
            r"\b(group|supergroup)\b.{0,40}\b(investigate|risk|activity)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="investigate_user",
            label="Investigate User",
            retrieval_hint="user risk activity patterns notable evidence",
            tools=("risk", "behavior", "alerts", "personnel", "timeline", "relationship", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(investigate|profile|look\s*up|who\s+is)\b.{0,40}\b(user|person|"
            r"account|suspect)?|"
            r"\b(why|explain).{0,40}\b(high\s*risk|risky|suspicious)\b|"
            r"\bhigh\s*risk\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="keyword_analysis",
            label="Keyword Analysis",
            retrieval_hint="keyword phrase message hits matches",
            tools=("search", "alerts"),
            requires=("none",),
        ),
        re.compile(
            r"\b(keyword\s+analysis|analyze\s+keywords?|keyword\s+hits?|"
            r"search\s+for\s+keyword)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="risk_assessment",
            label="Risk Assessment",
            retrieval_hint="risk score factors severity contributors",
            tools=("risk", "alerts", "behavior", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(risk\s+assessment|assess\s+risk|risk\s+score|"
            r"how\s+risky)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="search_conversations",
            label="Search Conversations",
            retrieval_hint="conversation message search semantic",
            tools=("search",),
            requires=("none",),
        ),
        re.compile(
            r"\b(search\s+conversations?|find\s+messages?|conversation\s+search)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="find_similar_users",
            label="Find Similar Users",
            retrieval_hint="similar users related peers activity patterns",
            tools=("relationship", "behavior", "personnel", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(find\s+similar\s+users?|similar\s+(users?|accounts?)|"
            r"users?\s+like)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="summarize_case",
            label="Summarize Case",
            retrieval_hint="case summary investigation overview",
            tools=("risk", "behavior", "personnel", "alerts", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(summarize\s+(the\s+)?case|case\s+summary|summarise\s+case)\b",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="semantic_search",
            label="Semantic Search",
            retrieval_hint="semantic search similar messages activity",
            tools=("search",),
            requires=("none",),
        ),
        re.compile(
            r"\b(search|find|lookup|look\s*up)\b.{0,40}\b(message|keyword|"
            r"phrase|similar\s+activ)",
            re.I,
        ),
    ),
    (
        InvestigationIntent(
            key="summary",
            label="Summarize this investigation",
            retrieval_hint="investigation summary overview key findings subjects",
            tools=("risk", "behavior", "personnel", "search"),
            requires=("user",),
        ),
        re.compile(
            r"\b(summarize|summary|overview|brief)\b.{0,40}\b(investigation|case|subject)\b|"
            r"\bsummarize\s+this\b|"
            r"\binvestigation\s+summary\b",
            re.I,
        ),
    ),
)

_UNKNOWN = InvestigationIntent(
    key="unknown",
    label="Unknown",
    tools=(),
    requires=("none",),
    block_llm=True,
)

_INVESTIGATE_USER = InvestigationIntent(
    key="investigate_user",
    label="Investigate User",
    retrieval_hint="user risk activity patterns notable evidence",
    tools=("risk", "behavior", "alerts", "personnel", "timeline", "relationship", "search"),
    requires=("user",),
)

# Phrases that are clearly not an entity lookup.
_CHATTY_RE = re.compile(
    r"\b(joke|jokes|poem|story|stories|weather|recipe|homework|"
    r"write\s+code|hello|hi\b|hey\b|thanks|thank\s+you)\b",
    re.I,
)
# Bare target queries: names, @handles, telegram IDs (case-insensitive).
_ENTITY_QUERY_RE = re.compile(
    r"^(?:"
    r"@?[A-Za-z][A-Za-z0-9_.'-]{1,40}(?:\s+[A-Za-z][A-Za-z0-9_.'-]{1,40}){0,3}"
    r"|-?\d{5,}"
    r")$"
)
_GENERIC_ENTITY_WORDS = frozenset(
    {
        "user",
        "users",
        "person",
        "people",
        "group",
        "channel",
        "chat",
        "someone",
        "anyone",
        "this",
        "that",
        "unknown",
    }
)


# Question / investigation phrasing — not a bare entity paste.
_PROMPT_PHRASE_RE = re.compile(
    r"^\s*(?:why|what|how|when|where|who|show|list|find|explain|analyze|"
    r"analyse|investigate|generate|produce|create|write|summarize|compare|"
    r"open|go\s+to|describe|deep-?dive)\b|"
    r"\b(?:this\s+user|high\s+risk|behavioral?\s+anomal|dashboard\s+summary|"
    r"fleet\s+overview|investigation\s+summary|related\s+users)\b",
    re.I,
)


def _looks_like_entity_query(text: str) -> bool:
    """True when the analyst pasted a name / @handle / ID as the whole query."""
    t = (text or "").strip().rstrip("?.!")
    if not t or _CHATTY_RE.search(t):
        return False
    # Suggested prompts / intent sentences are never bare entity lookups.
    if _PROMPT_PHRASE_RE.search(t):
        return False
    if re.search(r"@[A-Za-z0-9_]{3,}", t):
        return True
    if re.search(r"(?<![\w])-?\d{5,}(?![\w])", t) and len(t.split()) <= 4:
        return True
    # Capitalized proper name as the bulk of a short query (not a sentence).
    if (
        re.fullmatch(
            r"[A-Z][a-zA-Z'`-]{1,30}(?:\s+[A-Z][a-zA-Z'`-]{1,30}){0,3}",
            t,
        )
        and len(t.split()) <= 4
    ):
        return True
    # Lowercase / mixed bare name queries e.g. "adib malay".
    if _ENTITY_QUERY_RE.match(t):
        tokens = [p.lower() for p in re.split(r"\s+", t) if p]
        if tokens and all(tok.lstrip("@") not in _GENERIC_ENTITY_WORDS for tok in tokens):
            return True
    return False


def classify_intent(question: str) -> InvestigationIntent:
    """Return the best-matching intent. Unknown never proceeds to the LLM."""
    text = (question or "").strip()
    if not text:
        return _UNKNOWN
    for intent, pattern in _PATTERNS:
        if pattern.search(text):
            return intent
    # Name / @username / Telegram ID lookups default to Investigate User.
    if _looks_like_entity_query(text):
        return _INVESTIGATE_USER
    return _UNKNOWN


def build_retrieval_question(
    question: str,
    intent: InvestigationIntent,
    *,
    subject: dict | None = None,
) -> str:
    """Expand the analyst question with intent/subject hints for retrieval only."""
    parts = [question.strip()]
    if intent.retrieval_hint:
        parts.append(f"Focus: {intent.retrieval_hint}")
    if subject:
        bits = []
        if subject.get("user_id") is not None:
            bits.append(f"user_id={subject['user_id']}")
        if subject.get("username"):
            bits.append(f"username=@{str(subject['username']).lstrip('@')}")
        if subject.get("display_name"):
            bits.append(f"name={subject['display_name']}")
        if subject.get("case_id"):
            bits.append(f"case_id={subject['case_id']}")
        if subject.get("alert_id") is not None:
            bits.append(f"alert_id={subject['alert_id']}")
        if bits:
            parts.append("Subject: " + ", ".join(bits))
    return "\n".join(parts)


def tools_for_intent(intent: InvestigationIntent) -> list[str]:
    """Deterministic tool plan for an intent."""
    return list(intent.tools)
