from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from recallops.database import health as database_health
from recallops.database.health import DatabaseNotReadyError, check_database_connection
from fastapi.testclient import TestClient

from recallops.api.routes.health import get_database_health_checker
from recallops.database.base import Base
from recallops.main import app
from recallops import models  # noqa: F401  # Register model metadata.


def test_database_health_success(client: TestClient) -> None:
    def successful_check() -> None:
        return None

    app.dependency_overrides[get_database_health_checker] = lambda: successful_check

    response = client.get("/api/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_database_health_failure_does_not_leak_driver_details(
    client: TestClient,
) -> None:
    sensitive_driver_detail = "fictional-db-host.example.invalid secret-password"

    def failed_check() -> None:
        raise RuntimeError(sensitive_driver_detail)

    app.dependency_overrides[get_database_health_checker] = lambda: failed_check

    response = client.get("/api/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert sensitive_driver_detail not in response.text


def test_database_health_requires_migrated_tables(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database_health, "get_engine", lambda: engine)

    try:
        try:
            check_database_connection()
        except DatabaseNotReadyError as error:
            assert "Database schema is not ready" in str(error)
        else:
            raise AssertionError("Expected database readiness failure")
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_database_health_succeeds_when_required_tables_exist(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
    monkeypatch.setattr(database_health, "get_engine", lambda: engine)

    try:
        check_database_connection()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
