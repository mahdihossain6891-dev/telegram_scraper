"""Fictional persona generation engine."""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Sequence
from uuid import UUID, uuid5

from simulator.constants import SIM_TELEGRAM_USER_ID_BASE
from simulator.generation_config import GenerationConfig
from simulator.logger import get_prefixed_logger
from simulator.personas.dataset_loader import (
    cities_by_country,
    first_names,
    interest_topics,
    interests_by_personality,
    last_names,
    supported_languages,
    username_parts,
)
from simulator.personas.profiles import Persona
from simulator.personas.templates import (
    PERSONALITY_TEMPLATES,
    ActivityProfile,
    PersonalityType,
    RiskProfile,
    WritingStyle,
)

_log = get_prefixed_logger("persona", name="generator")

_NS_PERSONA = UUID("a3b5c7d9-1111-4222-8333-444455556666")

_AGE_RANGES = ("13-17", "18-24", "25-34", "35-44", "45-54", "55+")
_GENDERS = ("male", "female", "non_binary", "prefer_not_to_say")
_EDUCATION_LEVELS = (
    "high_school",
    "undergraduate",
    "graduate",
    "postgraduate",
    "vocational",
    "self_taught",
)


class PersonaGenerator:
    """Generates deterministic fictional Telegram users."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        self._rng = random.Random(config.random_seed)
        self._used_usernames: set[str] = set()
        self._lang_countries = {
            entry["code"]: entry["countries"] for entry in supported_languages()
        }

    def generate(self, count: int) -> list[Persona]:
        personas: list[Persona] = []
        for index in range(count):
            persona = self.generate_one(index)
            personas.append(persona)
            _log.info("Generated User %s (@%s)", persona.display_name, persona.username)
        return personas

    def generate_one(self, index: int) -> Persona:
        language = self._pick_language()
        personality = self._pick_personality()
        template = PERSONALITY_TEMPLATES[personality]

        is_bot = personality in {PersonalityType.BOT, PersonalityType.SPAM_BOT}
        if not is_bot and self._rng.random() < self._config.bot_percentage:
            personality = PersonalityType.BOT if self._rng.random() < 0.7 else PersonalityType.SPAM_BOT
            template = PERSONALITY_TEMPLATES[personality]
            is_bot = True

        country, city, timezone, region = self._pick_location(language)
        first = self._rng.choice(first_names(language))
        last = self._rng.choice(last_names(language))
        display_name = f"{first} {last}"
        username = self._unique_username(first, last, index)
        activity = self._pick_activity(template.average_activity)
        risk = self._pick_risk(template.default_risk)
        writing_style = self._pick_writing_style(language, template.writing_style)

        low_msg, high_msg = template.avg_messages_per_day
        low_len, high_len = template.avg_message_length
        low_emoji, high_emoji = template.emoji_frequency
        low_del, high_del = template.deletion_rate
        low_edit, high_edit = template.editing_rate

        interests = self._pick_interests(personality)
        topics = self._rng.sample(
            interest_topics(), k=min(self._rng.randint(2, 5), len(interest_topics()))
        )
        online_hours = self._online_hours_for(activity)
        account_date = self._account_creation_date(index)

        verified = (
            not is_bot
            and personality
            in {
                PersonalityType.JOURNALIST,
                PersonalityType.NEWS_CHANNEL,
                PersonalityType.MODERATOR,
            }
            and self._rng.random() < self._config.verified_percentage * 3
        ) or (not is_bot and self._rng.random() < self._config.verified_percentage)

        persona_id = uuid5(_NS_PERSONA, f"{self._config.random_seed}:{index}")

        return Persona(
            id=persona_id,
            telegram_id=SIM_TELEGRAM_USER_ID_BASE + index,
            display_name=display_name,
            username=username,
            biography=self._biography(personality, city, country, interests),
            age_range=self._rng.choice(_AGE_RANGES),
            gender=self._rng.choice(_GENDERS) if self._config.include_gender else None,
            language=language,
            timezone=timezone,
            country=country,
            city=city,
            profession=personality.value.replace("_", " ").title(),
            education=self._rng.choice(_EDUCATION_LEVELS),
            interests=interests,
            favorite_topics=topics,
            activity_level=activity.value,
            risk_profile=risk.value,
            writing_style=writing_style.value,
            emoji_frequency=round(self._rng.uniform(low_emoji, high_emoji), 3),
            average_message_length=self._rng.randint(low_len, high_len),
            average_messages_per_day=round(self._rng.uniform(low_msg, high_msg), 1),
            average_replies=round(self._rng.uniform(0.1, 0.6), 2),
            average_forwards=round(self._rng.uniform(0.0, 0.25), 2),
            deletion_rate=round(self._rng.uniform(low_del, high_del), 3),
            editing_rate=round(self._rng.uniform(low_edit, high_edit), 3),
            online_hours=online_hours,
            weekend_activity=round(self._rng.uniform(0.1, 0.9), 2),
            night_activity=self._night_activity_for(activity),
            preferred_groups=[],
            relationship_capacity=self._rng.randint(20, 500),
            account_creation_date=account_date,
            profile_photo_exists=self._rng.random() > 0.15 if not is_bot else False,
            verified=verified,
            bot=is_bot,
            personality_type=personality.value,
        )

    def _pick_language(self) -> str:
        dist = self._config.language_distribution
        keys = list(dist.keys())
        weights = [dist[k] for k in keys]
        return self._rng.choices(keys, weights=weights, k=1)[0]

    def _pick_personality(self) -> PersonalityType:
        dist = self._config.profession_distribution
        keys = [PersonalityType(k) for k in dist]
        weights = [dist[k.value] for k in keys]
        return self._rng.choices(keys, weights=weights, k=1)[0]

    def _pick_activity(self, default: ActivityProfile) -> ActivityProfile:
        dist = self._config.activity_distribution
        keys = [ActivityProfile(k) for k in dist]
        weights = [dist[k.value] for k in keys]
        if self._rng.random() < 0.65:
            return self._rng.choices(keys, weights=weights, k=1)[0]
        return default

    def _pick_risk(self, default: RiskProfile) -> RiskProfile:
        dist = self._config.risk_distribution
        keys = [RiskProfile(k) for k in dist]
        weights = [dist[k.value] for k in keys]
        if self._rng.random() < 0.55:
            return self._rng.choices(keys, weights=weights, k=1)[0]
        return default

    def _pick_writing_style(
        self, language: str, default: WritingStyle
    ) -> WritingStyle:
        lang_entry = next(
            (e for e in supported_languages() if e["code"] == language), None
        )
        if lang_entry and self._rng.random() < 0.5:
            style_key = self._rng.choice(lang_entry["writing_styles"])
            try:
                return WritingStyle(style_key)
            except ValueError:
                pass
        return default

    def _pick_location(self, language: str) -> tuple[str, str, str, str]:
        countries = self._lang_countries.get(language, ["United States"])
        country = self._rng.choice(countries)
        city_data = self._rng.choice(cities_by_country().get(country, [{"city": "Unknown", "timezone": "UTC", "region": "Global"}]))
        return country, city_data["city"], city_data["timezone"], city_data.get("region", "Global")

    def _unique_username(self, first: str, last: str, index: int) -> str:
        roots, suffixes = username_parts()
        base = f"{first}{last[0]}".lower()
        base = "".join(c for c in base if c.isalnum()) or roots[index % len(roots)]
        candidate = base
        attempt = 0
        while candidate.lower() in self._used_usernames:
            suffix = suffixes[attempt % len(suffixes)]
            candidate = f"{base}_{suffix}{index + attempt}"
            attempt += 1
        self._used_usernames.add(candidate.lower())
        return candidate[:32]

    def _pick_interests(self, personality: PersonalityType) -> list[str]:
        by_type = interests_by_personality()
        pool = by_type.get(personality.value, interest_topics())
        count = min(self._rng.randint(3, 6), len(pool))
        return self._rng.sample(pool, k=count)

    def _biography(
        self,
        personality: PersonalityType,
        city: str,
        country: str,
        interests: Sequence[str],
    ) -> str:
        interest_str = ", ".join(interests[:3])
        templates = {
            PersonalityType.STUDENT: f"Student in {city}. Into {interest_str}.",
            PersonalityType.DEVELOPER: f"Software developer based in {city}. {interest_str}.",
            PersonalityType.CYBERSECURITY_RESEARCHER: f"Security researcher | {city} | {interest_str}",
            PersonalityType.CRYPTO_TRADER: f"Trader. DYOR. {interest_str}.",
            PersonalityType.BUSINESS_OWNER: f"Founder in {country}. Focus: {interest_str}.",
            PersonalityType.TEACHER: f"Educator in {city}. Passionate about {interest_str}.",
            PersonalityType.JOURNALIST: f"Journalist covering {interest_str} in {region_hint(country)}.",
            PersonalityType.CONTENT_CREATOR: f"Creator from {city} ✨ {interest_str}",
            PersonalityType.MARKETPLACE_SELLER: f"Seller | {city} | {interest_str}",
            PersonalityType.MODERATOR: f"Community mod. {city}. {interest_str}.",
            PersonalityType.NEWS_CHANNEL: f"News updates — {interest_str}",
            PersonalityType.CASUAL_USER: f"Just vibing in {city}. Likes {interest_str}.",
            PersonalityType.BOT: "Automated assistant bot.",
            PersonalityType.SPAM_BOT: "Limited profile.",
        }
        return templates.get(personality, f"User from {city}, {country}.")

    def _online_hours_for(self, activity: ActivityProfile) -> list[int]:
        mapping = {
            ActivityProfile.MORNING_USER: list(range(6, 12)),
            ActivityProfile.NIGHT_OWL: list(range(20, 24)) + list(range(0, 3)),
            ActivityProfile.OFFICE_HOURS: list(range(9, 18)),
            ActivityProfile.WEEKEND_ONLY: list(range(10, 22)),
            ActivityProfile.ALWAYS_ONLINE: list(range(0, 24)),
            ActivityProfile.OCCASIONAL_USER: self._rng.sample(range(24), k=4),
            ActivityProfile.HIGHLY_ACTIVE: list(range(8, 23)),
            ActivityProfile.LURKER: self._rng.sample(range(24), k=2),
            ActivityProfile.INACTIVE: [],
        }
        return mapping.get(activity, list(range(9, 17)))

    def _night_activity_for(self, activity: ActivityProfile) -> float:
        night_map = {
            ActivityProfile.NIGHT_OWL: (0.6, 0.95),
            ActivityProfile.MORNING_USER: (0.0, 0.15),
            ActivityProfile.INACTIVE: (0.0, 0.05),
            ActivityProfile.LURKER: (0.05, 0.25),
        }
        low, high = night_map.get(activity, (0.1, 0.45))
        return round(self._rng.uniform(low, high), 2)

    def _account_creation_date(self, index: int) -> date:
        days_ago = 30 + (index * 17) % (365 * 5)
        return date.today() - timedelta(days=days_ago)


def region_hint(country: str) -> str:
    return country
