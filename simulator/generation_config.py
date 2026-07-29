"""Configuration for persona and group world generation (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.constants import DEFAULT_GROUP_COUNT, DEFAULT_USER_COUNT, GENERATION_PRESETS


def _default_language_distribution() -> dict[str, float]:
    return {
        "english": 0.35,
        "bengali": 0.25,
        "hindi": 0.15,
        "urdu": 0.10,
        "arabic": 0.08,
        "malay": 0.07,
    }


def english_only_language_distribution() -> dict[str, float]:
    """Single-language distribution for console simulation."""
    return {"english": 1.0}


def _default_activity_distribution() -> dict[str, float]:
    return {
        "morning_user": 0.12,
        "night_owl": 0.14,
        "office_hours": 0.18,
        "weekend_only": 0.08,
        "always_online": 0.06,
        "occasional_user": 0.16,
        "highly_active": 0.10,
        "lurker": 0.10,
        "inactive": 0.06,
    }


def _default_profession_distribution() -> dict[str, float]:
    return {
        "student": 0.14,
        "developer": 0.12,
        "cybersecurity_researcher": 0.05,
        "crypto_trader": 0.06,
        "business_owner": 0.06,
        "teacher": 0.05,
        "journalist": 0.04,
        "content_creator": 0.08,
        "marketplace_seller": 0.07,
        "moderator": 0.04,
        "news_channel": 0.02,
        "casual_user": 0.22,
        "bot": 0.03,
        "spam_bot": 0.02,
    }


def _default_risk_distribution() -> dict[str, float]:
    return {
        "normal": 0.70,
        "elevated": 0.18,
        "high": 0.09,
        "critical": 0.03,
    }


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Controls fictional user and group generation."""

    user_count: int = DEFAULT_USER_COUNT
    group_count: int = DEFAULT_GROUP_COUNT
    random_seed: int | None = 42
    language_distribution: dict[str, float] = field(
        default_factory=_default_language_distribution
    )
    activity_distribution: dict[str, float] = field(
        default_factory=_default_activity_distribution
    )
    profession_distribution: dict[str, float] = field(
        default_factory=_default_profession_distribution
    )
    risk_distribution: dict[str, float] = field(default_factory=_default_risk_distribution)
    bot_percentage: float = 0.03
    verified_percentage: float = 0.05
    include_gender: bool = True
    min_groups_per_user: int = 2
    max_groups_per_user: int = 8
    simulation_speed_multiplier: float = 720.0
    average_conversation_length: int = 12
    maximum_concurrent_conversations: int = 6
    average_replies: float = 0.72
    average_delay_seconds: int = 180
    message_length_multiplier: float = 1.0
    reply_probability: float = 0.72
    reaction_probability: float = 0.18
    forward_probability: float = 0.05
    media_probability: float = 0.08
    edit_probability: float = 0.06
    delete_probability: float = 0.03
    max_thread_messages: int = 60
    keyword_category: str | None = None

    def __post_init__(self) -> None:
        if self.user_count < 0 or self.group_count < 0:
            raise ValueError("user_count and group_count must be non-negative.")
        if not 0.0 <= self.bot_percentage <= 1.0:
            raise ValueError("bot_percentage must be between 0 and 1.")
        if not 0.0 <= self.verified_percentage <= 1.0:
            raise ValueError("verified_percentage must be between 0 and 1.")
        for field_name in (
            "average_replies",
            "reply_probability",
            "reaction_probability",
            "forward_probability",
            "media_probability",
            "edit_probability",
            "delete_probability",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1.")
        if self.simulation_speed_multiplier <= 0:
            raise ValueError("simulation_speed_multiplier must be positive.")
        if self.average_conversation_length < 2:
            raise ValueError("average_conversation_length must be at least 2.")
        if self.maximum_concurrent_conversations < 1:
            raise ValueError("maximum_concurrent_conversations must be positive.")
        if self.average_delay_seconds < 1:
            raise ValueError("average_delay_seconds must be positive.")
        if self.message_length_multiplier <= 0:
            raise ValueError("message_length_multiplier must be positive.")
        if self.max_thread_messages < 2:
            raise ValueError("max_thread_messages must be at least 2.")

    @classmethod
    def preset(cls, user_count: int, *, random_seed: int | None = 42) -> GenerationConfig:
        """Build a config for a standard preset size (10, 100, 500, 1000, 5000)."""
        if user_count not in GENERATION_PRESETS:
            raise ValueError(f"Unsupported preset {user_count}. Use {GENERATION_PRESETS}.")
        group_count = max(2, user_count // 10)
        return cls(user_count=user_count, group_count=group_count, random_seed=random_seed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_count": self.user_count,
            "group_count": self.group_count,
            "random_seed": self.random_seed,
            "language_distribution": dict(self.language_distribution),
            "activity_distribution": dict(self.activity_distribution),
            "profession_distribution": dict(self.profession_distribution),
            "risk_distribution": dict(self.risk_distribution),
            "bot_percentage": self.bot_percentage,
            "verified_percentage": self.verified_percentage,
            "include_gender": self.include_gender,
            "min_groups_per_user": self.min_groups_per_user,
            "max_groups_per_user": self.max_groups_per_user,
            "simulation_speed_multiplier": self.simulation_speed_multiplier,
            "average_conversation_length": self.average_conversation_length,
            "maximum_concurrent_conversations": self.maximum_concurrent_conversations,
            "average_replies": self.average_replies,
            "average_delay_seconds": self.average_delay_seconds,
            "message_length_multiplier": self.message_length_multiplier,
            "reply_probability": self.reply_probability,
            "reaction_probability": self.reaction_probability,
            "forward_probability": self.forward_probability,
            "media_probability": self.media_probability,
            "edit_probability": self.edit_probability,
            "delete_probability": self.delete_probability,
            "max_thread_messages": self.max_thread_messages,
        }
