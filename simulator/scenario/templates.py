"""Built-in scenario template definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.conversation.templates import ConversationLength, ConversationType
from simulator.scenario.labels import (
    ExpectedRiskLevel,
    InvestigationOutcome,
    ScenarioCategory,
    ScenarioDifficulty,
    ScenarioPriority,
)


@dataclass(frozen=True, slots=True)
class VocabularyProfile:
    """Terminology and style hints for conversation generation."""

    common_terms: tuple[str, ...]
    topic_keywords: tuple[str, ...]
    writing_style: str
    pacing: str
    typical_message_length: tuple[int, int]
    common_emojis: tuple[str, ...] = ()
    abbreviations: tuple[str, ...] = ()
    language_preferences: tuple[str, ...] = ("english",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "common_terms": list(self.common_terms),
            "topic_keywords": list(self.topic_keywords),
            "writing_style": self.writing_style,
            "pacing": self.pacing,
            "typical_message_length": list(self.typical_message_length),
            "common_emojis": list(self.common_emojis),
            "abbreviations": list(self.abbreviations),
            "language_preferences": list(self.language_preferences),
        }


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """Hidden evaluation metadata — never emitted in conversation text."""

    expected_risk_level: ExpectedRiskLevel
    expected_alert: bool
    expected_keywords: tuple[str, ...]
    expected_entities: tuple[str, ...]
    expected_relationships: tuple[str, ...]
    expected_behavioral_score: float
    expected_investigation_outcome: InvestigationOutcome
    expected_confidence: float
    synthetic_evaluation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_risk_level": self.expected_risk_level.value,
            "expected_alert": self.expected_alert,
            "expected_keywords": list(self.expected_keywords),
            "expected_entities": list(self.expected_entities),
            "expected_relationships": list(self.expected_relationships),
            "expected_behavioral_score": self.expected_behavioral_score,
            "expected_investigation_outcome": self.expected_investigation_outcome.value,
            "expected_confidence": self.expected_confidence,
            "synthetic_evaluation": self.synthetic_evaluation,
        }


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """Full scenario blueprint."""

    scenario_id: str
    name: str
    category: ScenarioCategory
    description: str
    difficulty: ScenarioDifficulty
    weight: float
    priority: ScenarioPriority
    expected_participants: tuple[int, int]
    expected_conversation_length: ConversationLength
    expected_activity: str
    vocabulary: VocabularyProfile
    languages: tuple[str, ...]
    conversation_style: str
    behavior_pattern: str
    expected_risk_category: str
    expected_relationship_growth: float
    expected_alert_count: int
    expected_investigation_complexity: str
    conversation_types: tuple[ConversationType, ...]
    typical_topics: tuple[str, ...]
    conversation_flow: tuple[str, ...]
    posting_behaviour: str
    group_activity: str
    preferred_personality_types: tuple[str, ...] = ()
    ground_truth: GroundTruth | None = None
    enabled: bool = True
    opener_templates: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "difficulty": self.difficulty.value,
            "weight": self.weight,
            "priority": self.priority.value,
            "expected_participants": list(self.expected_participants),
            "expected_conversation_length": self.expected_conversation_length.value,
            "expected_activity": self.expected_activity,
            "vocabulary": self.vocabulary.to_dict(),
            "languages": list(self.languages),
            "conversation_style": self.conversation_style,
            "behavior_pattern": self.behavior_pattern,
            "expected_risk_category": self.expected_risk_category,
            "expected_relationship_growth": self.expected_relationship_growth,
            "expected_alert_count": self.expected_alert_count,
            "expected_investigation_complexity": self.expected_investigation_complexity,
            "typical_topics": list(self.typical_topics),
            "enabled": self.enabled,
        }


def _normal_ground_truth() -> GroundTruth:
    return GroundTruth(
        expected_risk_level=ExpectedRiskLevel.NORMAL,
        expected_alert=False,
        expected_keywords=(),
        expected_entities=(),
        expected_relationships=(),
        expected_behavioral_score=0.1,
        expected_investigation_outcome=InvestigationOutcome.NO_ACTION,
        expected_confidence=0.2,
    )


def _synthetic_ground_truth(
    *,
    risk: ExpectedRiskLevel,
    keywords: tuple[str, ...],
    entities: tuple[str, ...],
    alert: bool = True,
    outcome: InvestigationOutcome = InvestigationOutcome.REVIEW,
) -> GroundTruth:
    return GroundTruth(
        expected_risk_level=risk,
        expected_alert=alert,
        expected_keywords=keywords,
        expected_entities=entities,
        expected_relationships=("seller_buyer", "coordinator_recruit"),
        expected_behavioral_score=0.75 if risk == ExpectedRiskLevel.HIGH else 0.9,
        expected_investigation_outcome=outcome,
        expected_confidence=0.85,
        synthetic_evaluation=True,
    )


def builtin_scenario_templates() -> list[ScenarioDefinition]:
    """Return all built-in scenario templates."""
    return [
        ScenarioDefinition(
            scenario_id="general_chat",
            name="General Chat",
            category=ScenarioCategory.GENERAL_CHAT,
            description="Casual community chatter.",
            difficulty=ScenarioDifficulty.LOW,
            weight=0.08,
            priority=ScenarioPriority.LOW,
            expected_participants=(2, 5),
            expected_conversation_length=ConversationLength.SHORT,
            expected_activity="occasional",
            vocabulary=VocabularyProfile(
                common_terms=("hey", "anyone", "thoughts", "today"),
                topic_keywords=("chat", "weekend", "plans"),
                writing_style="casual",
                pacing="relaxed",
                typical_message_length=(10, 60),
                common_emojis=("🙂", "👍"),
            ),
            languages=("english", "bengali", "hindi"),
            conversation_style="friendly",
            behavior_pattern="reactive",
            expected_risk_category="normal",
            expected_relationship_growth=0.2,
            expected_alert_count=0,
            expected_investigation_complexity="low",
            conversation_types=(ConversationType.CASUAL_CHAT, ConversationType.DISCUSSION),
            typical_topics=("weekend plans", "weather", "food"),
            conversation_flow=("greeting", "small_talk", "wrap_up"),
            posting_behaviour="low_frequency",
            group_activity="steady",
            preferred_personality_types=("casual_user", "student"),
            ground_truth=_normal_ground_truth(),
            opener_templates=("Good morning everyone.", "Anyone around today?"),
        ),
        ScenarioDefinition(
            scenario_id="technology",
            name="Technology",
            category=ScenarioCategory.TECHNOLOGY,
            description="Gadgets, startups, and innovation discussion.",
            difficulty=ScenarioDifficulty.LOW,
            weight=0.25,
            priority=ScenarioPriority.NORMAL,
            expected_participants=(3, 6),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="office_hours",
            vocabulary=VocabularyProfile(
                common_terms=("stack", "release", "benchmark", "roadmap"),
                topic_keywords=("cloud", "hardware", "startup", "saas"),
                writing_style="technical",
                pacing="moderate",
                typical_message_length=(30, 140),
            ),
            languages=("english",),
            conversation_style="informative",
            behavior_pattern="collaborative",
            expected_risk_category="normal",
            expected_relationship_growth=0.35,
            expected_alert_count=0,
            expected_investigation_complexity="low",
            conversation_types=(ConversationType.DISCUSSION, ConversationType.NEWS_SHARING),
            typical_topics=("cloud computing", "startups", "gadgets"),
            conversation_flow=("topic_intro", "comparison", "follow_up"),
            posting_behaviour="moderate",
            group_activity="weekday_peak",
            preferred_personality_types=("developer", "business_owner", "content_creator"),
            ground_truth=_normal_ground_truth(),
        ),
        ScenarioDefinition(
            scenario_id="programming",
            name="Programming",
            category=ScenarioCategory.PROGRAMMING,
            description="Code, tooling, and debugging discussions.",
            difficulty=ScenarioDifficulty.MEDIUM,
            weight=0.20,
            priority=ScenarioPriority.NORMAL,
            expected_participants=(2, 6),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="night_owl",
            vocabulary=VocabularyProfile(
                common_terms=("docker", "api", "deploy", "debug", "refactor"),
                topic_keywords=("python", "javascript", "linux", "devops"),
                writing_style="technical",
                pacing="focused",
                typical_message_length=(25, 180),
                abbreviations=("imo", "fwiw", "tbh"),
            ),
            languages=("english",),
            conversation_style="helpful",
            behavior_pattern="problem_solving",
            expected_risk_category="normal",
            expected_relationship_growth=0.4,
            expected_alert_count=0,
            expected_investigation_complexity="medium",
            conversation_types=(
                ConversationType.QUESTION,
                ConversationType.HELP_REQUEST,
                ConversationType.PROBLEM_SOLVING,
                ConversationType.TUTORIAL,
            ),
            typical_topics=("docker", "kubernetes", "debugging", "open source"),
            conversation_flow=("question", "clarification", "solution", "validation"),
            posting_behaviour="high_frequency",
            group_activity="evening_peak",
            preferred_personality_types=("developer", "student", "cybersecurity_researcher"),
            ground_truth=_normal_ground_truth(),
            opener_templates=(
                "Anyone using Docker Desktop lately?",
                "Need help debugging a deployment issue.",
            ),
        ),
        ScenarioDefinition(
            scenario_id="university",
            name="University",
            category=ScenarioCategory.UNIVERSITY,
            description="Campus life, assignments, and study groups.",
            difficulty=ScenarioDifficulty.LOW,
            weight=0.15,
            priority=ScenarioPriority.NORMAL,
            expected_participants=(3, 7),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="afternoon",
            vocabulary=VocabularyProfile(
                common_terms=("assignment", "lecture", "exam", "group project"),
                topic_keywords=("campus", "study", "notes"),
                writing_style="casual",
                pacing="bursty",
                typical_message_length=(15, 90),
            ),
            languages=("english", "bengali"),
            conversation_style="collaborative",
            behavior_pattern="study_group",
            expected_risk_category="normal",
            expected_relationship_growth=0.45,
            expected_alert_count=0,
            expected_investigation_complexity="low",
            conversation_types=(ConversationType.HELP_REQUEST, ConversationType.DISCUSSION),
            typical_topics=("assignments", "exams", "campus events"),
            conversation_flow=("question", "resource_share", "planning"),
            posting_behaviour="semester_cycle",
            group_activity="afternoon_evening",
            preferred_personality_types=("student", "teacher"),
            ground_truth=_normal_ground_truth(),
        ),
        ScenarioDefinition(
            scenario_id="marketplace",
            name="Marketplace",
            category=ScenarioCategory.MARKETPLACE,
            description="Buy/sell listings and negotiation.",
            difficulty=ScenarioDifficulty.MEDIUM,
            weight=0.10,
            priority=ScenarioPriority.NORMAL,
            expected_participants=(2, 4),
            expected_conversation_length=ConversationLength.SHORT,
            expected_activity="weekend",
            vocabulary=VocabularyProfile(
                common_terms=("price", "condition", "pickup", "available", "negotiable"),
                topic_keywords=("listing", "warranty", "delivery"),
                writing_style="casual",
                pacing="transactional",
                typical_message_length=(12, 70),
            ),
            languages=("english", "bengali", "malay"),
            conversation_style="promotional",
            behavior_pattern="transactional",
            expected_risk_category="elevated",
            expected_relationship_growth=0.15,
            expected_alert_count=0,
            expected_investigation_complexity="medium",
            conversation_types=(ConversationType.MARKETPLACE_LISTING, ConversationType.ANNOUNCEMENT),
            typical_topics=("electronics", "furniture", "services"),
            conversation_flow=("listing", "inquiry", "negotiation"),
            posting_behaviour="listing_driven",
            group_activity="weekend_peak",
            preferred_personality_types=("marketplace_seller", "casual_user", "moderator"),
            ground_truth=_normal_ground_truth(),
        ),
        ScenarioDefinition(
            scenario_id="gaming",
            name="Gaming",
            category=ScenarioCategory.GAMING,
            description="Games, esports, and co-op planning.",
            difficulty=ScenarioDifficulty.LOW,
            weight=0.10,
            priority=ScenarioPriority.LOW,
            expected_participants=(3, 8),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="evening",
            vocabulary=VocabularyProfile(
                common_terms=("ranked", "lobby", "patch", "grind"),
                topic_keywords=("fps", "rpg", "mobile", "esports"),
                writing_style="uses_slang",
                pacing="fast",
                typical_message_length=(8, 50),
                common_emojis=("🎮", "🔥"),
            ),
            languages=("english",),
            conversation_style="playful",
            behavior_pattern="social",
            expected_risk_category="normal",
            expected_relationship_growth=0.5,
            expected_alert_count=0,
            expected_investigation_complexity="low",
            conversation_types=(ConversationType.CASUAL_CHAT, ConversationType.DISCUSSION),
            typical_topics=("new releases", "ranked play", "co-op"),
            conversation_flow=("invite", "banter", "scheduling"),
            posting_behaviour="evening_bursts",
            group_activity="night_peak",
            preferred_personality_types=("student", "content_creator", "casual_user"),
            ground_truth=_normal_ground_truth(),
        ),
        ScenarioDefinition(
            scenario_id="news",
            name="News",
            category=ScenarioCategory.NEWS,
            description="Headlines and current events discussion.",
            difficulty=ScenarioDifficulty.MEDIUM,
            weight=0.10,
            priority=ScenarioPriority.HIGH,
            expected_participants=(2, 5),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="always_on",
            vocabulary=VocabularyProfile(
                common_terms=("breaking", "report", "source", "update"),
                topic_keywords=("headlines", "local", "economy"),
                writing_style="formal",
                pacing="reactive",
                typical_message_length=(40, 200),
            ),
            languages=("english", "arabic"),
            conversation_style="informative",
            behavior_pattern="broadcast",
            expected_risk_category="elevated",
            expected_relationship_growth=0.25,
            expected_alert_count=0,
            expected_investigation_complexity="medium",
            conversation_types=(ConversationType.NEWS_SHARING, ConversationType.DISCUSSION),
            typical_topics=("breaking news", "policy", "markets"),
            conversation_flow=("headline", "context", "debate"),
            posting_behaviour="event_driven",
            group_activity="continuous",
            preferred_personality_types=("journalist", "news_channel", "crypto_trader"),
            ground_truth=_normal_ground_truth(),
        ),
        ScenarioDefinition(
            scenario_id="synthetic_financial_fraud",
            name="Synthetic Financial Fraud Evaluation",
            category=ScenarioCategory.SYNTHETIC_THREAT_EVALUATION,
            description="Fictional scam-pattern dialogue for platform benchmarking only.",
            difficulty=ScenarioDifficulty.HIGH,
            weight=0.04,
            priority=ScenarioPriority.URGENT,
            expected_participants=(2, 4),
            expected_conversation_length=ConversationLength.MEDIUM,
            expected_activity="always_on",
            vocabulary=VocabularyProfile(
                common_terms=("transfer fee", "urgent payment", "verify account", "limited offer"),
                topic_keywords=("investment", "wallet", "guaranteed returns"),
                writing_style="grammar_mistakes",
                pacing="aggressive",
                typical_message_length=(15, 80),
            ),
            languages=("english",),
            conversation_style="coercive",
            behavior_pattern="scam_campaign",
            expected_risk_category="high",
            expected_relationship_growth=0.6,
            expected_alert_count=2,
            expected_investigation_complexity="high",
            conversation_types=(ConversationType.ANNOUNCEMENT, ConversationType.DISCUSSION),
            typical_topics=("investment scheme", "account verification"),
            conversation_flow=("hook", "pressure", "payment_request"),
            posting_behaviour="spam_burst",
            group_activity="continuous",
            preferred_personality_types=("spam_bot", "marketplace_seller", "crypto_trader"),
            ground_truth=_synthetic_ground_truth(
                risk=ExpectedRiskLevel.HIGH,
                keywords=("transfer fee", "verify account", "guaranteed returns", "urgent payment"),
                entities=("synthetic_wallet", "synthetic_recruiter"),
                outcome=InvestigationOutcome.ESCALATE,
            ),
            opener_templates=("Limited-time opportunity — DM for details.",),
        ),
        ScenarioDefinition(
            scenario_id="synthetic_counterfeit_docs",
            name="Synthetic Counterfeit Documents Evaluation",
            category=ScenarioCategory.SYNTHETIC_THREAT_EVALUATION,
            description="Fictional document-fraud indicators for evaluation only.",
            difficulty=ScenarioDifficulty.CRITICAL,
            weight=0.03,
            priority=ScenarioPriority.URGENT,
            expected_participants=(2, 3),
            expected_conversation_length=ConversationLength.SHORT,
            expected_activity="night_owl",
            vocabulary=VocabularyProfile(
                common_terms=("express service", "document package", "no questions", "discrete pickup"),
                topic_keywords=("passport copy", "license template", "rush order"),
                writing_style="very_short",
                pacing="covert",
                typical_message_length=(10, 45),
            ),
            languages=("english", "urdu"),
            conversation_style="evasive",
            behavior_pattern="covert_transaction",
            expected_risk_category="critical",
            expected_relationship_growth=0.7,
            expected_alert_count=3,
            expected_investigation_complexity="critical",
            conversation_types=(ConversationType.MARKETPLACE_LISTING, ConversationType.DISCUSSION),
            typical_topics=("document service", "rush delivery"),
            conversation_flow=("inquiry", "terms", "handoff"),
            posting_behaviour="low_visibility_burst",
            group_activity="night_peak",
            preferred_personality_types=("spam_bot", "marketplace_seller"),
            ground_truth=_synthetic_ground_truth(
                risk=ExpectedRiskLevel.CRITICAL,
                keywords=("document package", "discrete pickup", "rush order", "no questions"),
                entities=("synthetic_vendor", "synthetic_buyer"),
                outcome=InvestigationOutcome.CASE_OPEN,
            ),
        ),
        ScenarioDefinition(
            scenario_id="synthetic_narcotics_indicator",
            name="Synthetic Narcotics Indicator Evaluation",
            category=ScenarioCategory.SYNTHETIC_THREAT_EVALUATION,
            description="Fictional narcotics-related indicators for keyword/risk benchmarking.",
            difficulty=ScenarioDifficulty.CRITICAL,
            weight=0.03,
            priority=ScenarioPriority.URGENT,
            expected_participants=(2, 3),
            expected_conversation_length=ConversationLength.SHORT,
            expected_activity="night_owl",
            vocabulary=VocabularyProfile(
                common_terms=("package ready", "meet location", "cash only", "no trace"),
                topic_keywords=("delivery window", "quality check"),
                writing_style="uses_abbreviations",
                pacing="covert",
                typical_message_length=(8, 40),
                abbreviations=("omw", "asap"),
            ),
            languages=("english",),
            conversation_style="coded",
            behavior_pattern="covert_coordination",
            expected_risk_category="critical",
            expected_relationship_growth=0.8,
            expected_alert_count=3,
            expected_investigation_complexity="critical",
            conversation_types=(ConversationType.DISCUSSION, ConversationType.MARKETPLACE_LISTING),
            typical_topics=("package coordination", "pickup window"),
            conversation_flow=("signal", "coordination", "confirmation"),
            posting_behaviour="encrypted_style",
            group_activity="night_peak",
            preferred_personality_types=("spam_bot",),
            ground_truth=_synthetic_ground_truth(
                risk=ExpectedRiskLevel.CRITICAL,
                keywords=("package ready", "meet location", "cash only", "delivery window"),
                entities=("synthetic_courier", "synthetic_contact"),
                outcome=InvestigationOutcome.CASE_OPEN,
            ),
        ),
    ]
