"""Telegram Traffic Simulator — enterprise testing and demonstration framework.

This package is **dormant by default**. It does not modify the production
scraper, intelligence pipeline, or dashboard until explicitly enabled and
integrated in a future phase.
"""

from __future__ import annotations

from simulator.config import SimulationSettings, load_simulation_settings
from simulator.constants import PACKAGE_NAME, PACKAGE_VERSION
from simulator.contexts import AIContext, DatabaseContext, GraphContext
from simulator.environment import EnvironmentManager, EnvironmentService
from simulator.enums import (
    EnvironmentType,
    MessageSourceKind,
    SimulationSpeed,
    SimulationState,
)
from simulator.generation_config import GenerationConfig
from simulator.groups import Group, GroupCategory, GroupManager
from simulator.manager import SimulationManager
from simulator.models import (
    EnvironmentInformation,
    MessageEvent,
    SimulationConfiguration,
    SimulationStatus,
)
from simulator.personas.manager import PersonaManager
from simulator.personas.profiles import Persona
from simulator.sources import MessageSource, SimulationSource, TelethonSource
from simulator.statistics import WorldStatistics, compute_world_statistics
from simulator.scenario import ScenarioConfig, ScenarioManager
from simulator.execution import ExecutionConfig, SimulationExecutionEngine, SimulationSession, SessionStatus
from simulator.world_generator import GeneratedWorld, WorldGenerator

__all__ = [
    "AIContext",
    "DatabaseContext",
    "EnvironmentInformation",
    "EnvironmentManager",
    "EnvironmentService",
    "EnvironmentType",
    "ExecutionConfig",
    "GeneratedWorld",
    "GenerationConfig",
    "GraphContext",
    "Group",
    "GroupCategory",
    "GroupManager",
    "MessageEvent",
    "MessageSource",
    "MessageSourceKind",
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "Persona",
    "PersonaManager",
    "ScenarioConfig",
    "ScenarioManager",
    "SimulationConfiguration",
    "SimulationExecutionEngine",
    "SimulationSession",
    "SessionStatus",
    "SimulationManager",
    "SimulationSettings",
    "SimulationSource",
    "SimulationSpeed",
    "SimulationState",
    "SimulationStatus",
    "TelethonSource",
    "WorldGenerator",
    "WorldStatistics",
    "compute_world_statistics",
    "load_simulation_settings",
]

__version__ = PACKAGE_VERSION
