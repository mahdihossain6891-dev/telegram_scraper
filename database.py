"""Database engine, session management, and initialization helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import Settings, ensure_directories, load_settings
from models import Base, Chat, Message
from utils import get_logger

logger = get_logger("database")

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _sqlite_connect_args(database_url: str) -> dict[str, object]:
    """Return connect_args suitable for SQLite URLs."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enable foreign key enforcement for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a cached SQLAlchemy engine for the configured database."""
    global _ENGINE

    cfg = settings or load_settings()
    if _ENGINE is None:
        _ENGINE = create_engine(
            cfg.database_url,
            connect_args=_sqlite_connect_args(cfg.database_url),
            future=True,
        )
        if cfg.database_url.startswith("sqlite"):
            event.listen(_ENGINE, "connect", _enable_sqlite_foreign_keys)
        logger.debug("Database engine created for %s", cfg.database_url)
    return _ENGINE


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return a cached session factory bound to the application engine."""
    global _SESSION_FACTORY

    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(settings),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SESSION_FACTORY


def init_db(settings: Settings | None = None) -> None:
    """Create all database tables if they do not exist."""
    cfg = ensure_directories(settings)
    cfg.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = get_engine(cfg)
    Base.metadata.create_all(engine)
    logger.info("Database initialized at %s", cfg.database_path)


@contextmanager
def get_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Clear cached engine and session factory (used in tests)."""
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None


def message_exists(session: Session, chat_id: int, message_id: int) -> bool:
    """Return True if a message with the given Telegram IDs is already stored."""
    stmt = select(Message.id).where(
        Message.chat_id == chat_id,
        Message.message_id == message_id,
    )
    return session.scalar(stmt) is not None


def get_chat_by_id(session: Session, chat_id: int) -> Chat | None:
    """Return a chat by Telegram chat ID, or None if not found."""
    return session.get(Chat, chat_id)
