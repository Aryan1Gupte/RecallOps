from fastapi.testclient import TestClient

from recallops.ai.dependencies import get_embedding_service_factory
from recallops.ai.embedding_protocols import (
    EmbeddingResult,
    EmbeddingServiceError,
)
from recallops.main import app


def create_embedding_test_incident(client: TestClient) -> dict[str, str]:
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


class FakeEmbeddingService:
    def embed(self, text: str) -> EmbeddingResult:
        assert text == (
            "Title: Fictional checkout latency\n"
            "Description: Example requests are timing out.\n"
            "Service: checkout-api\n"
            "Environment: production\n"
            "Status: open"
        )
        return EmbeddingResult(
            vector=(0.0,) * 1024,
            dimension=1024,
            input_text_token_count=24,
            model_id="fake-titan-model",
        )


def test_embedding_preview_endpoint_returns_metadata_without_vector(
    client: TestClient,
) -> None:
    incident = create_embedding_test_incident(client)
    app.dependency_overrides[get_embedding_service_factory] = (
        lambda: lambda: FakeEmbeddingService()
    )

    response = client.post(
        f"/api/incidents/{incident['id']}/embedding-preview"
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "incident_id": incident["id"],
        "model_id": "fake-titan-model",
        "dimension": 1024,
        "input_text_token_count": 24,
        "text_preview": (
            "Title: Fictional checkout latency\n"
            "Description: Example requests are timing out.\n"
            "Service: checkout-api\n"
            "Environment: production\n"
            "Status: open"
        ),
    }
    assert "vector" not in body
    assert "embedding" not in body


def test_embedding_preview_returns_not_found_without_calling_provider(
    client: TestClient,
) -> None:
    provider_created = False

    def fail_if_called() -> FakeEmbeddingService:
        nonlocal provider_created
        provider_created = True
        return FakeEmbeddingService()

    app.dependency_overrides[get_embedding_service_factory] = lambda: fail_if_called

    response = client.post(
        "/api/incidents/00000000-0000-0000-0000-000000000001/embedding-preview"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert provider_created is False


def test_embedding_preview_rejects_invalid_uuid(client: TestClient) -> None:
    app.dependency_overrides[get_embedding_service_factory] = (
        lambda: lambda: FakeEmbeddingService()
    )

    response = client.post("/api/incidents/not-a-uuid/embedding-preview")

    assert response.status_code == 422


def test_embedding_service_failure_returns_safe_error(client: TestClient) -> None:
    incident = create_embedding_test_incident(client)
    private_provider_detail = "fictional account and request identifiers"

    class FailedEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise EmbeddingServiceError(private_provider_detail)

    app.dependency_overrides[get_embedding_service_factory] = (
        lambda: lambda: FailedEmbeddingService()
    )

    response = client.post(
        f"/api/incidents/{incident['id']}/embedding-preview"
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Embedding preview is temporarily unavailable"
    }
    assert private_provider_detail not in response.text
