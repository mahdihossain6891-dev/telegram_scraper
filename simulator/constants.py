"""Centralized simulator constants — avoid magic numbers in managers."""

from __future__ import annotations

PACKAGE_NAME = "telegram_traffic_simulator"
PACKAGE_VERSION = "0.7.0"

# Environment variable prefix for simulator settings.
ENV_PREFIX = "SIMULATION_"

# Default database names (isolated namespaces).
DEFAULT_LIVE_DATABASE_NAME = "telegram_scraper"
DEFAULT_SIMULATION_DATABASE_NAME = "telegram_scraper_simulation"

# Default paths (resolved relative to project root in config).
DEFAULT_LIVE_EXPORT_SUBDIR = "exports"
DEFAULT_SIMULATION_EXPORT_SUBDIR = "exports/simulator"

# Collection namespace strategy: separate databases (Phase 2 default).
COLLECTION_STRATEGY_SEPARATE_DATABASE = "separate_database"
COLLECTION_STRATEGY_PREFIX = "collection_prefix"

# Known Mongo collections used by the intelligence platform (metadata only).
KNOWN_COLLECTIONS = (
    "users",
    "chats",
    "messages",
    "extracted_entities",
    "user_activity",
    "behavioral_analytics",
    "alerts",
    "ai_sessions",
    "ai_reports",
)

# Manager defaults (overridden by SimulationSettings).
DEFAULT_USER_COUNT = 50
DEFAULT_GROUP_COUNT = 10
DEFAULT_SPEED = "realtime"

# Logging namespaces and prefixes.
LOG_NAMESPACE = "simulator"
LOG_PREFIX_SIMULATION = "[SIMULATION]"
LOG_PREFIX_ENVIRONMENT = "[ENVIRONMENT]"
LOG_PREFIX_SOURCE = "[SOURCE]"
LOG_PREFIX_PERSONA = "[PERSONA]"
LOG_PREFIX_GROUP = "[GROUP]"
LOG_PREFIX_GENERATOR = "[GENERATOR]"
LOG_PREFIX_CONVERSATION = "[CONVERSATION]"
LOG_PREFIX_SCHEDULER = "[SCHEDULER]"
LOG_PREFIX_REPLY = "[REPLY]"
LOG_PREFIX_THREAD = "[THREAD]"
LOG_PREFIX_SCENARIO = "[SCENARIO]"
LOG_PREFIX_EXECUTION = "[EXECUTION]"
LOG_PREFIX_PIPELINE = "[PIPELINE]"
LOG_PREFIX_EVENT = "[EVENT]"
LOG_PREFIX_METRICS = "[METRICS]"
LOG_MESSAGE_PREFIX = LOG_PREFIX_SIMULATION  # backwards compatible alias

# Fictional Telegram ID ranges (simulation-only; never overlap production assignment).
SIM_TELEGRAM_USER_ID_BASE = 9_000_000_000
SIM_TELEGRAM_CHAT_ID_BASE = -1_000_000_000_000

# Supported generation presets (user count).
GENERATION_PRESETS = (10, 100, 500, 1000, 5000)

# Metadata keys returned by managers.
META_VERSION_KEY = "package_version"
META_ENVIRONMENT_KEY = "environment"
META_STATE_KEY = "state"
META_ISOLATION_KEY = "strict_isolation"
