from fastapi.testclient import TestClient

from recallops.ai.bedrock import build_incident_analysis_service
from recallops.api.routes.health import get_database_health_checker
from recallops.config import get_settings
from recallops.main import app


def test_missing_bedrock_settings_do_not_break_non_ai_endpoints(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("BEDROCK_CHAT_MODEL_ID", raising=False)
    get_settings.cache_clear()
    build_incident_analysis_service.cache_clear()
    app.dependency_overrides[get_database_health_checker] = lambda: lambda: None

    try:
        health_response = client.get("/api/health")
        database_health_response = client.get("/api/health/database")
        incidents_response = client.get("/api/incidents")
    finally:
        get_settings.cache_clear()
        build_incident_analysis_service.cache_clear()

    assert health_response.status_code == 200
    assert database_health_response.status_code == 200
    assert incidents_response.status_code == 200
