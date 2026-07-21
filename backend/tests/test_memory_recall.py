from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from recallops.ai.dependencies import get_embedding_service_factory
from recallops.ai.embedding_protocols import (
    EmbeddingResult,
    EmbeddingServiceError,
)
from recallops.api.routes.incidents import get_memory_recall_searcher
from recallops.main import app
from recallops.repositories.memories import SimilarMemoryRecord


def incident_payload(title: str = "Checkout latency") -> dict[str, str]:
    return {
        "title": title,
        "description": "Requests are timing out for fictional shoppers.",
        "service": "checkout-api",
        "environment": "production",
    }


def create_test_incident(client: TestClient, title: str = "Checkout latency") -> dict:
    response = client.post("/api/incidents", json=incident_payload(title))
    assert response.status_code == 201
    return response.json()


class FakeEmbeddingService:
    def __init__(self, vector: tuple[float, ...] | None = None) -> None:
        self.inputs: list[str] = []
        self.vector = vector or (1.0,) + (0.0,) * 1023

    def embed(self, text: str) -> EmbeddingResult:
        self.inputs.append(text)
        return EmbeddingResult(
            vector=self.vector,
            dimension=1024,
            input_text_token_count=24,
            model_id="fake-titan-model",
        )


def override_embedding_service(service: object) -> None:
    app.dependency_overrides[get_embedding_service_factory] = lambda: lambda: service


def override_memory_searcher(searcher: object) -> None:
    app.dependency_overrides[get_memory_recall_searcher] = lambda: searcher


def similar_memory(
    *,
    memory_id: str = "00000000-0000-0000-0000-000000000101",
    incident_id: str | None = None,
    memory_incident_service: str | None = None,
    status: str = "active",
    cosine_distance: float = 0.2,
    summary: str = "Cache flush restored checkout",
    success_count: int = 2,
    failure_count: int = 1,
    created_at: datetime | None = None,
) -> SimilarMemoryRecord:
    return SimilarMemoryRecord(
        memory_id=UUID(memory_id),
        incident_id=UUID(incident_id) if incident_id is not None else None,
        memory_incident_service=memory_incident_service,
        memory_type="resolution",
        summary=summary,
        root_cause="Workers held stale cache entries",
        resolution="Restarted checkout workers",
        embedding_model_id="fake-memory-model",
        embedding_dimension=1024,
        success_count=success_count,
        failure_count=failure_count,
        status=status,
        cosine_distance=cosine_distance,
        created_at=created_at
        or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_recall_endpoint_success_with_fake_embedding_and_repository(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    service = FakeEmbeddingService()
    override_embedding_service(service)
    search_calls: list[tuple[tuple[float, ...], int]] = []

    def fake_searcher(
        session: Session,
        query_vector: tuple[float, ...],
        limit: int,
    ) -> list[SimilarMemoryRecord]:
        assert session is db_session
        search_calls.append((query_vector, limit))
        return [
            similar_memory(
                incident_id=incident["id"],
                memory_incident_service="checkout-api",
                cosine_distance=0.25,
            )
        ]

    override_memory_searcher(fake_searcher)

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == incident["id"]
    assert body["query_embedding_model_id"] == "fake-titan-model"
    assert body["query_embedding_dimension"] == 1024
    assert body["min_similarity"] == 0.6
    assert body["top_k"] == 5
    assert body["message"] == (
        "Found 1 relevant active memory after semantic gating and deterministic ranking."
    )
    assert body["ranking_formula"] == (
        "final_score = 0.70 * semantic_similarity "
        "+ 0.20 * reliability + 0.10 * same_service_score"
    )
    assert body["candidate_count"] == 1
    assert body["returned_count"] == 1
    assert len(body["memories"]) == 1
    memory = body["memories"][0]
    assert memory == {
        "memory_id": "00000000-0000-0000-0000-000000000101",
        "incident_id": incident["id"],
        "memory_type": "resolution",
        "summary": "Cache flush restored checkout",
        "root_cause": "Workers held stale cache entries",
        "resolution": "Restarted checkout workers",
        "status": "active",
        "embedding_model_id": "fake-memory-model",
        "embedding_dimension": 1024,
        "success_count": 2,
        "failure_count": 1,
        "cosine_distance": 0.25,
        "similarity": 0.75,
        "reliability": 0.6,
        "same_service": True,
        "same_service_score": 1.0,
        "final_score": memory["final_score"],
        "rank": 1,
        "why_recalled": (
            "Passed semantic gate with 0.75 similarity; "
            "reliability 0.60 from 2 successes and 1 failure; "
            "same service match contributed to final ranking."
        ),
    }
    assert memory["final_score"] == pytest.approx(0.745)
    assert service.inputs == [
        "Title: Checkout latency\n"
        "Description: Requests are timing out for fictional shoppers.\n"
        "Service: checkout-api\n"
        "Environment: production\n"
        "Status: open"
    ]
    assert search_calls == [(service.vector, 20)]


def test_recall_returns_not_found_without_calling_provider(
    client: TestClient,
) -> None:
    provider_called = False
    search_called = False

    class Provider:
        def embed(self, text: str) -> EmbeddingResult:
            nonlocal provider_called
            provider_called = True
            return FakeEmbeddingService().embed(text)

    def fake_searcher(
        session: Session,
        query_vector: tuple[float, ...],
        limit: int,
    ) -> list[SimilarMemoryRecord]:
        nonlocal search_called
        search_called = True
        return []

    override_embedding_service(Provider())
    override_memory_searcher(fake_searcher)

    response = client.post(
        "/api/incidents/00000000-0000-0000-0000-000000000001/memory-recall"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert provider_called is False
    assert search_called is False


def test_recall_rejects_invalid_uuid(client: TestClient) -> None:
    response = client.post("/api/incidents/not-a-uuid/memory-recall")

    assert response.status_code == 422


def test_recall_embedding_failure_returns_safe_502(client: TestClient) -> None:
    incident = create_test_incident(client)
    private_provider_detail = "fictional account and request identifiers"

    class FailedEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise EmbeddingServiceError(private_provider_detail)

    override_embedding_service(FailedEmbeddingService())
    override_memory_searcher(lambda session, query_vector, limit: [])

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 502
    assert response.json() == {"detail": "Memory recall is temporarily unavailable"}
    assert private_provider_detail not in response.text


def test_recall_only_returns_active_memories(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000102",
                status="rejected",
                cosine_distance=0.01,
                summary="Inactive high-similarity memory",
            ),
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000103",
                status="active",
                cosine_distance=0.2,
                summary="Active memory",
            ),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert [memory["summary"] for memory in response.json()["memories"]] == [
        "Active memory"
    ]


def test_recall_semantic_gate_filters_below_default_threshold(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000104",
                cosine_distance=0.41,
                summary="Below threshold",
            ),
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000105",
                cosine_distance=0.39,
                summary="Above threshold",
            ),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert [memory["summary"] for memory in response.json()["memories"]] == [
        "Above threshold"
    ]


def test_recall_does_not_let_metadata_rescue_below_threshold_memories(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000106",
                memory_incident_service="checkout-api",
                cosine_distance=0.41,
                summary="Below threshold despite strong metadata",
                success_count=100,
                failure_count=0,
            ),
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000107",
                cosine_distance=0.39,
                summary="Semantically relevant memory",
                success_count=0,
                failure_count=0,
            ),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert [memory["summary"] for memory in response.json()["memories"]] == [
        "Semantically relevant memory"
    ]


def test_recall_top_k_defaults_to_five(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    limits: list[int] = []

    def fake_searcher(
        session: Session,
        query_vector: tuple[float, ...],
        limit: int,
    ) -> list[SimilarMemoryRecord]:
        limits.append(limit)
        return []

    override_memory_searcher(fake_searcher)

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert response.json()["top_k"] == 5
    assert limits == [20]


def test_recall_top_k_allows_ten_and_rejects_larger_values(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    limits: list[int] = []

    def fake_searcher(
        session: Session,
        query_vector: tuple[float, ...],
        limit: int,
    ) -> list[SimilarMemoryRecord]:
        limits.append(limit)
        return []

    override_memory_searcher(fake_searcher)

    valid_response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"top_k": 10},
    )
    invalid_response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"top_k": 11},
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["top_k"] == 10
    assert invalid_response.status_code == 422
    assert limits == [20]


def test_recall_applies_top_k_after_deterministic_ranking(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000108",
                cosine_distance=0.05,
                summary="Closest semantic candidate",
                success_count=0,
                failure_count=1,
            ),
            similar_memory(
                memory_id="00000000-0000-0000-0000-000000000109",
                memory_incident_service="checkout-api",
                cosine_distance=0.10,
                summary="Highest deterministic rank",
                success_count=10,
                failure_count=0,
            ),
        ]
    )

    response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"top_k": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] == 1
    assert body["memories"][0]["summary"] == "Highest deterministic rank"
    assert body["memories"][0]["rank"] == 1


def test_recall_min_similarity_validates_bounds(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(lambda session, query_vector, limit: [])

    low_response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"min_similarity": -0.01},
    )
    high_response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"min_similarity": 1.01},
    )
    valid_response = client.post(
        f"/api/incidents/{incident['id']}/memory-recall",
        params={"min_similarity": 0.75},
    )

    assert low_response.status_code == 422
    assert high_response.status_code == 422
    assert valid_response.status_code == 200
    assert valid_response.json()["min_similarity"] == 0.75


def test_recall_similarity_is_one_minus_cosine_distance(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(cosine_distance=0.1234),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert response.json()["memories"][0]["similarity"] == 0.8766


def test_public_recall_response_excludes_raw_vectors(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(cosine_distance=0.2),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert "query_vector" not in response.text
    assert "memory_vector" not in response.text
    assert '"embedding":' not in response.text
    assert "vector" not in response.text


def test_recall_returns_empty_list_when_no_memories_pass_gate(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_memory_searcher(
        lambda session, query_vector, limit: [
            similar_memory(cosine_distance=0.7),
        ]
    )

    response = client.post(f"/api/incidents/{incident['id']}/memory-recall")

    assert response.status_code == 200
    assert response.json()["memories"] == []
    assert response.json()["message"] == (
        "No relevant active memories passed the semantic gate for this incident."
    )
