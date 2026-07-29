"""Scenario taxonomy and evaluation labels."""

from __future__ import annotations

from enum import Enum


class ScenarioCategory(str, Enum):
    GENERAL_CHAT = "general_chat"
    TECHNOLOGY = "technology"
    PROGRAMMING = "programming"
    CYBERSECURITY = "cybersecurity"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    GAMING = "gaming"
    PHOTOGRAPHY = "photography"
    TRAVEL = "travel"
    MOVIES = "movies"
    MUSIC = "music"
    FITNESS = "fitness"
    BUSINESS = "business"
    UNIVERSITY = "university"
    MARKETPLACE = "marketplace"
    FINANCE = "finance"
    NEWS = "news"
    POLITICS = "politics"
    SPORTS = "sports"
    COOKING = "cooking"
    SYNTHETIC_THREAT_EVALUATION = "synthetic_threat_evaluation"


class ScenarioDifficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EvolutionPhase(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class ScenarioEventType(str, Enum):
    NEW_MEMBER = "new_member"
    MODERATOR_ANNOUNCEMENT = "moderator_announcement"
    PINNED_MESSAGE = "pinned_message"
    POLL = "poll"
    BREAKING_NEWS = "breaking_news"
    MARKETPLACE_LISTING = "marketplace_listing"
    TOPIC_CHANGE = "topic_change"
    QUESTION = "question"
    CONVERSATION_SPLIT = "conversation_split"


class ExpectedRiskLevel(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class InvestigationOutcome(str, Enum):
    NO_ACTION = "no_action"
    MONITOR = "monitor"
    REVIEW = "review"
    ESCALATE = "escalate"
    CASE_OPEN = "case_open"
