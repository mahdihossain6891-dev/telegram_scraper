"""Group engine — fictional Telegram groups."""

from __future__ import annotations

from simulator.groups.categories import GroupCategory
from simulator.groups.manager import GroupManager
from simulator.groups.membership import MembershipEngine
from simulator.groups.profiles import Group

__all__ = ["Group", "GroupCategory", "GroupManager", "MembershipEngine"]
