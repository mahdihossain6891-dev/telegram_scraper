"""MongoDB connection, indexes, and repository helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator
from urllib.parse import urlparse

from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase

from config import Settings, ensure_directories, load_settings
from models import Chat, ExtractedEntity, Message, User, utcnow
from utils import get_logger

logger = get_logger("database")

_CLIENT: MongoClient | None = None
_DB_NAME: str | None = None


class MongoSession:
    """Thin session wrapper that mirrors the old get_session() usage pattern."""

    def __init__(self, db: MongoDatabase) -> None:
        self.db = db

    @property
    def chats(self) -> Collection:
        return self.db["chats"]

    @property
    def users(self) -> Collection:
        return self.db["users"]

    @property
    def messages(self) -> Collection:
        return self.db["messages"]

    @property
    def entities(self) -> Collection:
        return self.db["extracted_entities"]

    @property
    def user_activity(self) -> Collection:
        return self.db["user_activity"]

    @property
    def behavioral_analytics(self) -> Collection:
        """Isolated Behavioral Analytics profiles (does not alter other collections)."""
        return self.db["behavioral_analytics"]

    @property
    def counters(self) -> Collection:
        return self.db["counters"]

    def next_id(self, name: str) -> int:
        result = self.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(result["seq"])

    def get_chat(self, chat_id: int) -> Chat | None:
        doc = self.chats.find_one({"_id": chat_id})
        return Chat.from_doc(doc) if doc else None

    def get_user(self, user_id: int) -> User | None:
        doc = self.users.find_one({"_id": user_id})
        return User.from_doc(doc) if doc else None

    def upsert_chat(self, chat: Chat) -> Chat:
        existing = self.get_chat(chat.id)
        now = utcnow()
        if existing is not None:
            self.chats.update_one(
                {"_id": chat.id},
                {
                    "$set": {
                        "title": chat.title,
                        "username": chat.username,
                        "chat_type": chat.chat_type,
                        "updated_at": now,
                    }
                },
            )
            existing.title = chat.title
            existing.username = chat.username
            existing.chat_type = chat.chat_type
            existing.updated_at = now
            return existing
        chat.created_at = now
        chat.updated_at = now
        self.chats.insert_one(chat.to_doc())
        return chat

    def upsert_user(self, user: User) -> User:
        existing = self.get_user(user.id)
        now = utcnow()
        if existing is not None:
            updates: dict[str, Any] = {"updated_at": now}
            if user.username is not None:
                updates["username"] = user.username
                existing.username = user.username
            if user.first_name is not None:
                updates["first_name"] = user.first_name
                existing.first_name = user.first_name
            if user.last_name is not None:
                updates["last_name"] = user.last_name
                existing.last_name = user.last_name
            self.users.update_one({"_id": user.id}, {"$set": updates})
            existing.updated_at = now
            return existing
        user.created_at = now
        user.updated_at = now
        self.users.insert_one(user.to_doc())
        return user

    def insert_message(self, message: Message) -> Message:
        message.id = self.next_id("messages")
        message.scraped_at = utcnow()
        self.messages.insert_one(message.to_doc())
        return message

    def insert_entity(self, entity: ExtractedEntity) -> ExtractedEntity:
        entity.id = self.next_id("entities")
        entity.created_at = utcnow()
        self.entities.insert_one(entity.to_doc())
        return entity

    def list_chats(self) -> list[Chat]:
        return [Chat.from_doc(doc) for doc in self.chats.find().sort("_id", ASCENDING)]

    def list_users(self) -> list[User]:
        return [User.from_doc(doc) for doc in self.users.find().sort("_id", ASCENDING)]

    def list_messages(self) -> list[Message]:
        return [Message.from_doc(doc) for doc in self.messages.find().sort("_id", ASCENDING)]

    def list_entities(self) -> list[ExtractedEntity]:
        return [
            ExtractedEntity.from_doc(doc)
            for doc in self.entities.find().sort("_id", ASCENDING)
        ]

    def delete_private_chats(self) -> dict[str, int]:
        private_ids = [
            int(doc["_id"])
            for doc in self.chats.find({"chat_type": "private chat"}, {"_id": 1})
        ]
        if not private_ids:
            return {"chats": 0, "messages": 0, "entities": 0}
        message_ids = [
            int(doc["_id"])
            for doc in self.messages.find({"chat_id": {"$in": private_ids}}, {"_id": 1})
        ]
        entities_deleted = 0
        if message_ids:
            entities_deleted = self.entities.delete_many(
                {"message_row_id": {"$in": message_ids}}
            ).deleted_count
        messages_deleted = self.messages.delete_many(
            {"chat_id": {"$in": private_ids}}
        ).deleted_count
        chats_deleted = self.chats.delete_many({"_id": {"$in": private_ids}}).deleted_count
        return {
            "chats": chats_deleted,
            "messages": messages_deleted,
            "entities": entities_deleted,
        }

    def drop_all_data(self) -> None:
        self.chats.delete_many({})
        self.users.delete_many({})
        self.messages.delete_many({})
        self.entities.delete_many({})
        self.user_activity.delete_many({})
        self.counters.delete_many({})


def _parse_mongo_settings(database_url: str) -> tuple[str, str]:
    """Return (connection_uri, database_name) from MONGODB_URI / DATABASE_URL."""
    raw = database_url.strip()
    if raw.startswith("mongodb://") or raw.startswith("mongodb+srv://"):
        parsed = urlparse(raw)
        db_name = (parsed.path or "").lstrip("/") or "telegram_scraper"
        # Strip db path for MongoClient when present
        if parsed.path and parsed.path != "/":
            # Rebuild URI without path for client; keep auth/query
            netloc = parsed.netloc
            query = f"?{parsed.query}" if parsed.query else ""
            uri = f"{parsed.scheme}://{netloc}/{query}" if query else f"{parsed.scheme}://{netloc}"
            # Better: use pymongo URI with database in path — MongoClient accepts full URI
            return raw, db_name
        return raw, db_name
    # Legacy sqlite URL — ignore and use local docker mongo
    return "mongodb://127.0.0.1:27017", "telegram_scraper"


def get_client(settings: Settings | None = None) -> MongoClient:
    """Return a cached MongoClient."""
    global _CLIENT, _DB_NAME
    cfg = settings or load_settings()
    uri, db_name = _parse_mongo_settings(cfg.database_url)
    if _CLIENT is None:
        _CLIENT = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _DB_NAME = db_name
        logger.debug("MongoDB client created for %s / %s", uri, db_name)
    return _CLIENT


def get_db(settings: Settings | None = None) -> MongoDatabase:
    """Return the application Mongo database."""
    cfg = settings or load_settings()
    _, db_name = _parse_mongo_settings(cfg.database_url)
    return get_client(cfg)[db_name]


def get_db_by_name(database_name: str, settings: Settings | None = None) -> MongoDatabase:
    """Return a named Mongo database on the same cluster as production."""
    cfg = settings or load_settings()
    return get_client(cfg)[database_name]


def get_simulation_database_name() -> str:
    """Isolated simulation database name (``telegram_scraper_simulation`` by default)."""
    from simulator.config import load_simulation_settings

    return load_simulation_settings().simulation_database_name


def init_db_indexes(session: MongoSession) -> None:
    """Ensure indexes exist on the given session database."""
    session.messages.create_index(
        [("chat_id", ASCENDING), ("message_id", ASCENDING)],
        unique=True,
        name="uq_messages_chat_message",
    )
    session.messages.create_index(
        [("chat_id", ASCENDING), ("timestamp", ASCENDING)],
        name="ix_messages_chat_timestamp",
    )
    session.messages.create_index(
        [("sender_id", ASCENDING), ("timestamp", ASCENDING)],
        name="ix_messages_sender_timestamp",
    )
    session.entities.create_index(
        [("entity_type", ASCENDING), ("entity_value", ASCENDING)],
        name="ix_entities_type_value",
    )
    session.entities.create_index([("message_row_id", ASCENDING)])
    session.users.create_index([("username", ASCENDING)])
    session.chats.create_index([("username", ASCENDING)])
    session.user_activity.create_index([("last_seen", ASCENDING)])
    session.user_activity.create_index([("suspicious_count", ASCENDING)])
    session.user_activity.create_index([("message_count", ASCENDING)])
    session.user_activity.create_index([("chat_ids", ASCENDING)])
    session.user_activity.create_index([("username", ASCENDING)])
    session.behavioral_analytics.create_index(
        [("user_id", ASCENDING)],
        unique=True,
        name="uq_behavioral_user",
    )
    session.behavioral_analytics.create_index(
        [("behavior_score", ASCENDING)],
        name="ix_behavioral_score",
    )
    session.behavioral_analytics.create_index(
        [("behavior_status", ASCENDING)],
        name="ix_behavioral_status",
    )
    session.behavioral_analytics.create_index(
        [("username", ASCENDING)],
        name="ix_behavioral_username",
    )
    session.behavioral_analytics.create_index(
        [("last_updated", -1)],
        name="ix_behavioral_updated",
    )


def init_db(settings: Settings | None = None) -> None:
    """Ensure indexes exist for MongoDB collections."""
    cfg = ensure_directories(settings)
    session = MongoSession(get_db(cfg))
    init_db_indexes(session)
    try:
        get_client(cfg).admin.command("ping")
    except Exception:
        # mongomock / offline environments still create indexes locally
        pass
    logger.info("MongoDB initialized (%s)", cfg.database_url)


@contextmanager
def get_session_for_database(
    database_name: str,
    settings: Settings | None = None,
) -> Generator[MongoSession, None, None]:
    """Open a session against a specific logical database (e.g. simulation)."""
    cfg = settings or load_settings()
    session = MongoSession(get_db_by_name(database_name, cfg))
    init_db_indexes(session)
    yield session


def clear_database(database_name: str, settings: Settings | None = None) -> None:
    """Drop all application collections in the given database."""
    with get_session_for_database(database_name, settings) as session:
        session.drop_all_data()
        session.behavioral_analytics.delete_many({})


def clear_simulation_database(settings: Settings | None = None) -> None:
    """Remove all simulation dummy data."""
    clear_database(get_simulation_database_name(), settings)


@contextmanager
def get_session(settings: Settings | None = None) -> Generator[MongoSession, None, None]:
    """Provide a MongoDB session wrapper."""
    cfg = settings or load_settings()
    yield MongoSession(get_db(cfg))


def reset_engine_cache() -> None:
    """Clear cached Mongo client (used in tests)."""
    global _CLIENT, _DB_NAME
    if _CLIENT is not None:
        _CLIENT.close()
    _CLIENT = None
    _DB_NAME = None


def message_exists(session: MongoSession, chat_id: int, message_id: int) -> bool:
    """Return True if a message with the given Telegram IDs is already stored."""
    return (
        session.messages.find_one({"chat_id": chat_id, "message_id": message_id}, {"_id": 1})
        is not None
    )


def get_chat_by_id(session: MongoSession, chat_id: int) -> Chat | None:
    """Return a chat by Telegram chat ID, or None if not found."""
    return session.get_chat(chat_id)


def database_available(settings: Settings | None = None) -> bool:
    """Return True if MongoDB is reachable."""
    try:
        cfg = settings or load_settings()
        get_client(cfg).admin.command("ping")
        return True
    except Exception:
        return False
