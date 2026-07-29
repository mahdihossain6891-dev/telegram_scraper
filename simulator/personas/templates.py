"""Personality templates, writing styles, and activity profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class WritingStyle(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    TECHNICAL = "technical"
    VERY_SHORT = "very_short"
    VERBOSE = "verbose"
    EMOJI_HEAVY = "emoji_heavy"
    EMOJI_FREE = "emoji_free"
    USES_SLANG = "uses_slang"
    USES_ABBREVIATIONS = "uses_abbreviations"
    GRAMMAR_MISTAKES = "grammar_mistakes"
    MIXES_ENGLISH_BENGALI = "mixes_english_bengali"
    MIXES_ENGLISH_HINDI = "mixes_english_hindi"
    MIXES_ENGLISH_URDU = "mixes_english_urdu"
    MIXES_ENGLISH_MALAY = "mixes_english_malay"
    UNUSUAL_PUNCTUATION = "unusual_punctuation"


class ActivityProfile(str, Enum):
    MORNING_USER = "morning_user"
    NIGHT_OWL = "night_owl"
    OFFICE_HOURS = "office_hours"
    WEEKEND_ONLY = "weekend_only"
    ALWAYS_ONLINE = "always_online"
    OCCASIONAL_USER = "occasional_user"
    HIGHLY_ACTIVE = "highly_active"
    LURKER = "lurker"
    INACTIVE = "inactive"


class RiskProfile(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class PersonalityType(str, Enum):
    STUDENT = "student"
    DEVELOPER = "developer"
    CYBERSECURITY_RESEARCHER = "cybersecurity_researcher"
    CRYPTO_TRADER = "crypto_trader"
    BUSINESS_OWNER = "business_owner"
    TEACHER = "teacher"
    JOURNALIST = "journalist"
    CONTENT_CREATOR = "content_creator"
    MARKETPLACE_SELLER = "marketplace_seller"
    MODERATOR = "moderator"
    NEWS_CHANNEL = "news_channel"
    CASUAL_USER = "casual_user"
    BOT = "bot"
    SPAM_BOT = "spam_bot"


@dataclass(frozen=True, slots=True)
class PersonalityTemplate:
    """Reusable personality blueprint for fictional users."""

    personality_type: PersonalityType
    writing_style: WritingStyle
    posting_frequency: str
    typical_interests: tuple[str, ...]
    emoji_usage: str
    language_preference: str
    average_activity: ActivityProfile
    conversation_style: str
    avg_messages_per_day: tuple[float, float]
    avg_message_length: tuple[int, int]
    emoji_frequency: tuple[float, float]
    deletion_rate: tuple[float, float]
    editing_rate: tuple[float, float]
    default_risk: RiskProfile

    def to_dict(self) -> dict[str, Any]:
        return {
            "personality_type": self.personality_type.value,
            "writing_style": self.writing_style.value,
            "posting_frequency": self.posting_frequency,
            "typical_interests": list(self.typical_interests),
            "emoji_usage": self.emoji_usage,
            "language_preference": self.language_preference,
            "average_activity": self.average_activity.value,
            "conversation_style": self.conversation_style,
        }


PERSONALITY_TEMPLATES: dict[PersonalityType, PersonalityTemplate] = {
    PersonalityType.STUDENT: PersonalityTemplate(
        personality_type=PersonalityType.STUDENT,
        writing_style=WritingStyle.CASUAL,
        posting_frequency="moderate",
        typical_interests=("education", "gaming", "music", "programming"),
        emoji_usage="medium",
        language_preference="mixed",
        average_activity=ActivityProfile.OFFICE_HOURS,
        conversation_style="reactive",
        avg_messages_per_day=(15, 45),
        avg_message_length=(20, 80),
        emoji_frequency=(0.15, 0.35),
        deletion_rate=(0.02, 0.08),
        editing_rate=(0.05, 0.15),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.DEVELOPER: PersonalityTemplate(
        personality_type=PersonalityType.DEVELOPER,
        writing_style=WritingStyle.TECHNICAL,
        posting_frequency="high",
        typical_interests=("programming", "open source", "linux", "cloud computing"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.NIGHT_OWL,
        conversation_style="helpful",
        avg_messages_per_day=(20, 60),
        avg_message_length=(40, 200),
        emoji_frequency=(0.02, 0.12),
        deletion_rate=(0.01, 0.05),
        editing_rate=(0.08, 0.20),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.CYBERSECURITY_RESEARCHER: PersonalityTemplate(
        personality_type=PersonalityType.CYBERSECURITY_RESEARCHER,
        writing_style=WritingStyle.TECHNICAL,
        posting_frequency="moderate",
        typical_interests=("cybersecurity", "privacy", "networking", "linux"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.NIGHT_OWL,
        conversation_style="analytical",
        avg_messages_per_day=(10, 35),
        avg_message_length=(50, 250),
        emoji_frequency=(0.0, 0.08),
        deletion_rate=(0.03, 0.10),
        editing_rate=(0.10, 0.25),
        default_risk=RiskProfile.ELEVATED,
    ),
    PersonalityType.CRYPTO_TRADER: PersonalityTemplate(
        personality_type=PersonalityType.CRYPTO_TRADER,
        writing_style=WritingStyle.USES_ABBREVIATIONS,
        posting_frequency="very_high",
        typical_interests=("cryptocurrency", "blockchain", "finance", "news"),
        emoji_usage="medium",
        language_preference="english",
        average_activity=ActivityProfile.ALWAYS_ONLINE,
        conversation_style="opinionated",
        avg_messages_per_day=(40, 120),
        avg_message_length=(15, 60),
        emoji_frequency=(0.10, 0.30),
        deletion_rate=(0.05, 0.15),
        editing_rate=(0.02, 0.08),
        default_risk=RiskProfile.HIGH,
    ),
    PersonalityType.BUSINESS_OWNER: PersonalityTemplate(
        personality_type=PersonalityType.BUSINESS_OWNER,
        writing_style=WritingStyle.PROFESSIONAL,
        posting_frequency="moderate",
        typical_interests=("business", "startups", "finance", "networking"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.OFFICE_HOURS,
        conversation_style="direct",
        avg_messages_per_day=(8, 25),
        avg_message_length=(30, 120),
        emoji_frequency=(0.0, 0.10),
        deletion_rate=(0.01, 0.04),
        editing_rate=(0.05, 0.12),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.TEACHER: PersonalityTemplate(
        personality_type=PersonalityType.TEACHER,
        writing_style=WritingStyle.FORMAL,
        posting_frequency="low",
        typical_interests=("education", "books", "science"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.MORNING_USER,
        conversation_style="explanatory",
        avg_messages_per_day=(5, 20),
        avg_message_length=(40, 150),
        emoji_frequency=(0.05, 0.15),
        deletion_rate=(0.01, 0.03),
        editing_rate=(0.06, 0.14),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.JOURNALIST: PersonalityTemplate(
        personality_type=PersonalityType.JOURNALIST,
        writing_style=WritingStyle.FORMAL,
        posting_frequency="high",
        typical_interests=("journalism", "news", "politics"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.OFFICE_HOURS,
        conversation_style="informative",
        avg_messages_per_day=(15, 50),
        avg_message_length=(60, 300),
        emoji_frequency=(0.0, 0.08),
        deletion_rate=(0.02, 0.06),
        editing_rate=(0.12, 0.30),
        default_risk=RiskProfile.ELEVATED,
    ),
    PersonalityType.CONTENT_CREATOR: PersonalityTemplate(
        personality_type=PersonalityType.CONTENT_CREATOR,
        writing_style=WritingStyle.EMOJI_HEAVY,
        posting_frequency="very_high",
        typical_interests=("photography", "music", "movies", "social media"),
        emoji_usage="high",
        language_preference="mixed",
        average_activity=ActivityProfile.HIGHLY_ACTIVE,
        conversation_style="engaging",
        avg_messages_per_day=(30, 90),
        avg_message_length=(10, 80),
        emoji_frequency=(0.25, 0.55),
        deletion_rate=(0.03, 0.10),
        editing_rate=(0.04, 0.12),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.MARKETPLACE_SELLER: PersonalityTemplate(
        personality_type=PersonalityType.MARKETPLACE_SELLER,
        writing_style=WritingStyle.CASUAL,
        posting_frequency="high",
        typical_interests=("marketplace", "business", "finance"),
        emoji_usage="medium",
        language_preference="mixed",
        average_activity=ActivityProfile.OFFICE_HOURS,
        conversation_style="promotional",
        avg_messages_per_day=(25, 70),
        avg_message_length=(20, 100),
        emoji_frequency=(0.12, 0.28),
        deletion_rate=(0.04, 0.12),
        editing_rate=(0.03, 0.09),
        default_risk=RiskProfile.ELEVATED,
    ),
    PersonalityType.MODERATOR: PersonalityTemplate(
        personality_type=PersonalityType.MODERATOR,
        writing_style=WritingStyle.PROFESSIONAL,
        posting_frequency="moderate",
        typical_interests=("moderation", "community", "networking"),
        emoji_usage="low",
        language_preference="english",
        average_activity=ActivityProfile.ALWAYS_ONLINE,
        conversation_style="authoritative",
        avg_messages_per_day=(20, 55),
        avg_message_length=(25, 120),
        emoji_frequency=(0.02, 0.10),
        deletion_rate=(0.01, 0.04),
        editing_rate=(0.05, 0.15),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.NEWS_CHANNEL: PersonalityTemplate(
        personality_type=PersonalityType.NEWS_CHANNEL,
        writing_style=WritingStyle.FORMAL,
        posting_frequency="very_high",
        typical_interests=("news", "journalism"),
        emoji_usage="none",
        language_preference="english",
        average_activity=ActivityProfile.ALWAYS_ONLINE,
        conversation_style="broadcast",
        avg_messages_per_day=(50, 150),
        avg_message_length=(80, 400),
        emoji_frequency=(0.0, 0.02),
        deletion_rate=(0.01, 0.03),
        editing_rate=(0.15, 0.35),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.CASUAL_USER: PersonalityTemplate(
        personality_type=PersonalityType.CASUAL_USER,
        writing_style=WritingStyle.CASUAL,
        posting_frequency="low",
        typical_interests=("food", "travel", "movies", "music"),
        emoji_usage="medium",
        language_preference="mixed",
        average_activity=ActivityProfile.OCCASIONAL_USER,
        conversation_style="friendly",
        avg_messages_per_day=(3, 15),
        avg_message_length=(10, 60),
        emoji_frequency=(0.10, 0.30),
        deletion_rate=(0.02, 0.08),
        editing_rate=(0.03, 0.10),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.BOT: PersonalityTemplate(
        personality_type=PersonalityType.BOT,
        writing_style=WritingStyle.TECHNICAL,
        posting_frequency="automated",
        typical_interests=("automation",),
        emoji_usage="none",
        language_preference="english",
        average_activity=ActivityProfile.ALWAYS_ONLINE,
        conversation_style="scripted",
        avg_messages_per_day=(100, 500),
        avg_message_length=(20, 100),
        emoji_frequency=(0.0, 0.02),
        deletion_rate=(0.0, 0.01),
        editing_rate=(0.0, 0.01),
        default_risk=RiskProfile.NORMAL,
    ),
    PersonalityType.SPAM_BOT: PersonalityTemplate(
        personality_type=PersonalityType.SPAM_BOT,
        writing_style=WritingStyle.GRAMMAR_MISTAKES,
        posting_frequency="spam",
        typical_interests=("marketplace", "cryptocurrency"),
        emoji_usage="high",
        language_preference="english",
        average_activity=ActivityProfile.ALWAYS_ONLINE,
        conversation_style="aggressive",
        avg_messages_per_day=(200, 1000),
        avg_message_length=(5, 40),
        emoji_frequency=(0.30, 0.70),
        deletion_rate=(0.10, 0.30),
        editing_rate=(0.0, 0.02),
        default_risk=RiskProfile.CRITICAL,
    ),
}


SUPPORTED_LANGUAGES = frozenset(
    {"english", "bengali", "hindi", "urdu", "arabic", "malay"}
)

VALID_ACTIVITY_PROFILES = frozenset(p.value for p in ActivityProfile)
VALID_RISK_PROFILES = frozenset(p.value for p in RiskProfile)
VALID_WRITING_STYLES = frozenset(s.value for s in WritingStyle)
