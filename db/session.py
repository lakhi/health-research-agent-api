from typing import Generator

from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.url import get_db_url

_db_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_db_url_cached: str | None = None


def get_db_url_cached() -> str:
    """Return cached DB URL, computing it on first access."""
    global _db_url_cached

    if _db_url_cached is None:
        _db_url_cached = get_db_url()

    return _db_url_cached


# Backward-compatible export for modules that import db_url directly.
db_url: str = get_db_url_cached()


def get_engine() -> Engine:
    """Return SQLAlchemy engine, creating it lazily on first access."""
    global _db_engine

    if _db_engine is None:
        _db_engine = create_engine(get_db_url_cached(), pool_pre_ping=True)

    return _db_engine


def get_session_factory() -> sessionmaker[Session]:
    """Return SQLAlchemy sessionmaker, creating it lazily on first access."""
    global _session_factory

    if _session_factory is None:
        _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

    return _session_factory


class _LazySessionLocal:
    """Callable wrapper that preserves SessionLocal() usage while deferring initialization."""

    def __call__(self) -> Session:
        return get_session_factory()()


SessionLocal = _LazySessionLocal()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields:
        Session: An SQLAlchemy database session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
