from fastapi.testclient import TestClient

from recallops.api.routes.health import get_database_health_checker
from recallops.main import app


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
