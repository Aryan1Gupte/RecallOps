"""Process-wide SQLAlchemy engine and synchronous session lifecycle."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from recallops.config import get_settings
from recallops.database.url import normalize_database_url


@lru_cache
def get_engine() -> Engine:
    """Create one safely configured engine for the application process."""

    database_url = get_settings().require_database_url()
    return create_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True,
        hide_parameters=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create one reusable synchronous session factory."""

    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    """Provide a request-scoped database session and always close it."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
