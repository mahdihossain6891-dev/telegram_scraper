"""Tests for activity scheduling."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid5, UUID

from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scheduler.activity import is_persona_active
from simulator.scheduler.manager import SchedulerManager


def _persona(*, name: str, activity: str, online_hours: list[int]) -> Persona:
    return Persona(
        id=uuid5(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), name),
        telegram_id=9_000_000_000 + len(name),
        display_name=name,
        username=name.lower(),
        biography="test",
        age_range="25-34",
        gender="male",
        language="english",
        timezone="UTC",
        country="United Kingdom",
        city="London",
        profession="Developer",
        education="graduate",
        interests=["programming", "linux"],
        favorite_topics=["python", "docker"],
        activity_level=activity,
        risk_profile="normal",
        writing_style="technical",
        emoji_frequency=0.0,
        average_message_length=60,
        average_messages_per_day=20.0,
        average_replies=0.6,
        average_forwards=0.1,
        deletion_rate=0.01,
        editing_rate=0.05,
        online_hours=online_hours,
        weekend_activity=0.5,
        night_activity=0.2,
        preferred_groups=[],
        relationship_capacity=100,
        account_creation_date=date(2024, 1, 1),
        profile_photo_exists=True,
        verified=False,
        bot=False,
        personality_type="developer",
    )


def _group(member_ids: list[str]) -> Group:
    return Group(
        id=uuid5(UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"), "group"),
        telegram_chat_id=-1000,
        name="Dev Group",
        description="Test group",
        category="programming",
        language="english",
        region="United Kingdom",
        privacy="public",
        maximum_members=500,
        current_members=len(member_ids),
        creation_date=date(2024, 1, 1),
        owner_id=member_ids[0],
        moderator_ids=[],
        activity_level="high",
        average_daily_messages=100.0,
        topic_tags=["python", "docker"],
        member_ids=member_ids,
    )


class TestScheduler:
    def test_activity_profiles_follow_hours(self) -> None:
        office = _persona(name="Office", activity="office_hours", online_hours=list(range(9, 18)))
        night = _persona(name="Night", activity="night_owl", online_hours=[21, 22, 23, 0, 1])
        assert is_persona_active(office, datetime(2026, 1, 5, 10, 0, 0))
        assert not is_persona_active(office, datetime(2026, 1, 5, 23, 0, 0))
        assert is_persona_active(night, datetime(2026, 1, 5, 23, 0, 0))
        assert not is_persona_active(night, datetime(2026, 1, 5, 10, 0, 0))

    def test_scheduler_selects_active_users(self) -> None:
        active = _persona(name="Active", activity="office_hours", online_hours=list(range(9, 18)))
        sleeping = _persona(name="Sleeping", activity="night_owl", online_hours=[21, 22, 23])
        group = _group([str(active.id), str(sleeping.id)])
        manager = SchedulerManager(
            GenerationConfig(random_seed=12),
            start_time=datetime(2026, 1, 5, 10, 0, 0),
        )
        chosen = manager.active_users_for_group([active, sleeping], group)
        assert [persona.username for persona in chosen] == ["active"]

    def test_scheduler_advances_time(self) -> None:
        persona = _persona(name="Poster", activity="office_hours", online_hours=list(range(9, 18)))
        group = _group([str(persona.id)])
        manager = SchedulerManager(
            GenerationConfig(random_seed=12, average_delay_seconds=30),
            start_time=datetime(2026, 1, 5, 10, 0, 0),
        )
        before = manager.current_time
        after = manager.advance_for_message(persona, group, is_reply=False, index=0)
        assert after > before
