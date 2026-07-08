from uuid import UUID

from fastapi.testclient import TestClient

from recallops.ai.bedrock import AnalysisServiceError
from recallops.ai.dependencies import get_incident_analysis_service_factory
from recallops.ai.protocols import IncidentAnalysisInput
from recallops.main import app
from recallops.schemas.analysis import IncidentAnalysisResponse


def create_test_incident(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/incidents",
        json={
            "title": "Fictional checkout latency",
            "description": "Example requests are timing out.",
            "service": "checkout-api",
            "environment": "production",
        },
    )
    assert response.status_code == 201
    return response.json()


class FakeAnalysisService:
    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        return IncidentAnalysisResponse(
            incident_id=incident.incident_id,
            summary="The fictional checkout service is experiencing elevated latency.",
            likely_category="service latency",
            hypotheses=["A downstream dependency may be responding slowly."],
            recommended_next_steps=["Inspect recent dependency latency metrics."],
            cautions=["This is an initial hypothesis, not a confirmed root cause."],
            model_id="fake-analysis-model",
        )


def test_analysis_endpoint_success(client: TestClient) -> None:
    incident = create_test_incident(client)
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    response = client.post(f"/api/incidents/{incident['id']}/analysis")

    assert response.status_code == 200
    assert response.json() == {
        "incident_id": incident["id"],
        "summary": "The fictional checkout service is experiencing elevated latency.",
        "likely_category": "service latency",
        "hypotheses": ["A downstream dependency may be responding slowly."],
        "recommended_next_steps": ["Inspect recent dependency latency metrics."],
        "cautions": ["This is an initial hypothesis, not a confirmed root cause."],
        "model_id": "fake-analysis-model",
    }


def test_analysis_endpoint_returns_not_found_without_calling_ai(
    client: TestClient,
) -> None:
    service_created = False

    def fail_if_called() -> FakeAnalysisService:
        nonlocal service_created
        service_created = True
        return FakeAnalysisService()

    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: fail_if_called
    )

    response = client.post(
        "/api/incidents/00000000-0000-0000-0000-000000000001/analysis"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert service_created is False


def test_analysis_endpoint_rejects_invalid_uuid(client: TestClient) -> None:
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    response = client.post("/api/incidents/not-a-uuid/analysis")

    assert response.status_code == 422


def test_analysis_service_failure_returns_safe_error(client: TestClient) -> None:
    incident = create_test_incident(client)
    private_driver_detail = "fictional account and request identifiers"

    class FailedAnalysisService:
        def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
            raise AnalysisServiceError(private_driver_detail)

    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FailedAnalysisService()
    )

    response = client.post(f"/api/incidents/{incident['id']}/analysis")

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis is temporarily unavailable"}
    assert private_driver_detail not in response.text


def test_analysis_response_incident_id_is_a_uuid(client: TestClient) -> None:
    incident = create_test_incident(client)
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    response = client.post(f"/api/incidents/{incident['id']}/analysis")

    assert UUID(response.json()["incident_id"]) == UUID(incident["id"])
