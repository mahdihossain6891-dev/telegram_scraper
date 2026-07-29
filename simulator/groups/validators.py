"""Group validation rules."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from simulator.exceptions import GroupValidationError
from simulator.groups.profiles import Group
from simulator.personas.templates import SUPPORTED_LANGUAGES


def validate_group(group: Group) -> None:
    errors: list[str] = []
    if not isinstance(group.id, UUID):
        errors.append("id must be a UUID")
    if group.telegram_chat_id >= 0:
        errors.append("telegram_chat_id must be negative for groups")
    if not group.name.strip():
        errors.append("name is required")
    if group.language not in SUPPORTED_LANGUAGES:
        errors.append(f"unsupported language: {group.language}")
    if group.maximum_members < 1:
        errors.append("maximum_members must be positive")
    if group.current_members < 0:
        errors.append("current_members must be non-negative")
    if group.current_members > group.maximum_members:
        errors.append("current_members cannot exceed maximum_members")
    if group.current_members > 0 and not group.owner_id:
        errors.append("owner_id is required when the group has members")

    if errors:
        raise GroupValidationError("; ".join(errors))


def validate_unique_groups(groups: Iterable[Group]) -> None:
    uuids: set[str] = set()
    chat_ids: set[int] = set()
    names: set[str] = set()
    for group in groups:
        uid = str(group.id)
        if uid in uuids:
            raise GroupValidationError(f"duplicate group UUID: {uid}")
        uuids.add(uid)
        if group.telegram_chat_id in chat_ids:
            raise GroupValidationError(f"duplicate telegram_chat_id: {group.telegram_chat_id}")
        chat_ids.add(group.telegram_chat_id)
        name_key = group.name.lower()
        if name_key in names:
            raise GroupValidationError(f"duplicate group name: {group.name}")
        names.add(name_key)
        validate_group(group)


def validate_membership_integrity(
    groups: Iterable[Group],
    *,
    known_persona_ids: set[str],
) -> None:
    for group in groups:
        if not group.member_ids:
            continue
        if group.owner_id and group.owner_id not in known_persona_ids:
            raise GroupValidationError(
                f"group {group.name} owner {group.owner_id} is not a known persona"
            )
        for mod_id in group.moderator_ids:
            if mod_id not in known_persona_ids:
                raise GroupValidationError(
                    f"group {group.name} moderator {mod_id} is not a known persona"
                )
        for member_id in group.member_ids:
            if member_id not in known_persona_ids:
                raise GroupValidationError(
                    f"group {group.name} member {member_id} is not a known persona"
                )
        if group.owner_id and group.owner_id not in group.member_ids:
            raise GroupValidationError(f"group {group.name} owner must be a member")
