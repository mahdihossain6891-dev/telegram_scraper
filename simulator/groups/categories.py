"""Group categories for fictional Telegram groups."""

from __future__ import annotations

from enum import Enum


class GroupCategory(str, Enum):
    PROGRAMMING = "programming"
    TECHNOLOGY = "technology"
    CYBERSECURITY = "cybersecurity"
    GAMING = "gaming"
    PHOTOGRAPHY = "photography"
    UNIVERSITY = "university"
    MOVIES = "movies"
    MUSIC = "music"
    TRAVEL = "travel"
    FOOD = "food"
    FITNESS = "fitness"
    GENERAL_DISCUSSION = "general_discussion"
    MARKETPLACE = "marketplace"
    CRYPTO = "crypto"
    FINANCE = "finance"
    NEWS = "news"
    BUSINESS = "business"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    SCIENCE = "science"
    BOOKS = "books"


GROUP_CATEGORY_TOPICS: dict[GroupCategory, tuple[str, ...]] = {
    GroupCategory.PROGRAMMING: ("python", "javascript", "open source", "coding help"),
    GroupCategory.TECHNOLOGY: ("gadgets", "startups", "innovation", "hardware"),
    GroupCategory.CYBERSECURITY: ("infosec", "pentest", "malware", "privacy"),
    GroupCategory.GAMING: ("pc gaming", "mobile games", "esports", "rpg"),
    GroupCategory.PHOTOGRAPHY: ("street photo", "portraits", "editing", "gear"),
    GroupCategory.UNIVERSITY: ("assignments", "campus life", "study groups"),
    GroupCategory.MOVIES: ("reviews", "streaming", "bollywood", "hollywood"),
    GroupCategory.MUSIC: ("playlists", "concerts", "production", "lyrics"),
    GroupCategory.TRAVEL: ("backpacking", "visa tips", "itineraries", "hotels"),
    GroupCategory.FOOD: ("recipes", "restaurants", "street food", "cooking"),
    GroupCategory.FITNESS: ("gym", "running", "nutrition", "yoga"),
    GroupCategory.GENERAL_DISCUSSION: ("chat", "off-topic", "community"),
    GroupCategory.MARKETPLACE: ("buy", "sell", "classifieds", "deals"),
    GroupCategory.CRYPTO: ("bitcoin", "altcoins", "trading", "defi"),
    GroupCategory.FINANCE: ("investing", "stocks", "personal finance"),
    GroupCategory.NEWS: ("breaking news", "headlines", "local news"),
    GroupCategory.BUSINESS: ("entrepreneurship", "networking", "saas"),
    GroupCategory.ARTIFICIAL_INTELLIGENCE: ("llm", "ml", "agents", "research"),
    GroupCategory.SCIENCE: ("physics", "biology", "space", "research"),
    GroupCategory.BOOKS: ("fiction", "non-fiction", "reading club"),
}

ALL_CATEGORIES = tuple(GroupCategory)
