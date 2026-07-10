from fastapi.testclient import TestClient

from recallops.ai.dependencies import get_incident_analysis_service_factory
from recallops.ai.protocols import IncidentAnalysisInput
from recallops.ai.titan import build_embedding_service
from recallops.api.routes.health import get_database_health_checker
from recallops.config import get_settings
from recallops.main import app
from recallops.schemas.analysis import IncidentAnalysisResponse


class FakeAnalysisService:
    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        return IncidentAnalysisResponse(
            incident_id=incident.incident_id,
            summary="Fictional safe analysis.",
            likely_category="test",
            hypotheses=["Fictional hypothesis."],
            recommended_next_steps=["Fictional next step."],
            cautions=[],
            model_id="fake-analysis-model",
        )


def test_missing_embedding_settings_do_not_break_non_embedding_endpoints(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.delenv("BEDROCK_EMBEDDING_MODEL_ID", raising=False)
    get_settings.cache_clear()
    build_embedding_service.cache_clear()
    app.dependency_overrides[get_database_health_checker] = lambda: lambda: None
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    try:
        health_response = client.get("/api/health")
        database_health_response = client.get("/api/health/database")
        create_response = client.post(
            "/api/incidents",
            json={
                "title": "Fictional incident",
                "description": "Example description.",
                "service": "example-service",
                "environment": "test",
            },
        )
        incident_id = create_response.json()["id"]
        analysis_response = client.post(
            f"/api/incidents/{incident_id}/analysis"
        )
        list_memories_response = client.get("/api/memories")
    finally:
        get_settings.cache_clear()
        build_embedding_service.cache_clear()

    assert health_response.status_code == 200
    assert database_health_response.status_code == 200
    assert create_response.status_code == 201
    assert analysis_response.status_code == 200
    assert list_memories_response.status_code == 200
