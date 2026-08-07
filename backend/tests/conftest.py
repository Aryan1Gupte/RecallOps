from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from recallops.database.base import Base
from recallops.database.session import get_db
from recallops.main import app
from recallops import models  # noqa: F401  # Register model metadata.
from recallops.api.rate_limit import reset_ai_rate_limiter_for_tests
from recallops.config import get_settings


@pytest.fixture(autouse=True)
def reset_process_config_and_rate_limits() -> Generator[None, None, None]:
    """Keep process-local deployment controls from leaking between tests."""

    get_settings.cache_clear()
    reset_ai_rate_limiter_for_tests()
    yield
    get_settings.cache_clear()
    reset_ai_rate_limiter_for_tests()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated, in-memory database for each test."""

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        yield session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Use dependency overrides so tests never access CockroachDB Cloud."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
