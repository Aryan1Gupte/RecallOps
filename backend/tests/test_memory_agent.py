import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from recallops.ai.bedrock import (
    BedrockMemoryAssistedRecommendationService,
    MemoryAssistedRecommendationServiceError,
)
from recallops.ai.dependencies import (
    get_embedding_service_factory,
    get_memory_assisted_recommendation_service_factory,
)
from recallops.ai.embedding_protocols import EmbeddingResult
from recallops.ai.protocols import (
    IncidentAnalysisInput,
    MemoryAssistedRecommendationResult,
)
from recallops.api.rate_limit import reset_ai_rate_limiter_for_tests
from recallops.api.routes.incidents import get_memory_recall_searcher
from recallops.config import get_settings
from recallops.main import app
from recallops.repositories.memories import SimilarMemoryRecord
from recallops.schemas.agent import ModelMemoryAssistedRecommendationPayload
from recallops.schemas.memory import RecalledMemoryResponse


def create_test_incident(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/incidents",
        json={
            "title": "Checkout latency recurrence",
            "description": "Checkout requests are timing out again.",
            "service": "checkout-api",
            "environment": "production",
        },
    )
    assert response.status_code == 201
    return response.json()


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.inputs: list[str] = []
        self.vector = (1.0,) + (0.0,) * 1023

    def embed(self, text: str) -> EmbeddingResult:
        self.inputs.append(text)
        return EmbeddingResult(
            vector=self.vector,
            dimension=1024,
            input_text_token_count=28,
            model_id="fake-titan-model",
        )


class FakeRecommendationService:
    def __init__(
        self,
        payload: ModelMemoryAssistedRecommendationPayload | None = None,
        db_session: Session | None = None,
    ) -> None:
        self.calls: list[tuple[IncidentAnalysisInput, list[RecalledMemoryResponse]]] = []
        self.in_transaction_during_call: bool | None = None
        self._db_session = db_session
        self._payload = payload or ModelMemoryAssistedRecommendationPayload(
            summary="Checkout latency resembles prior stale-cache incidents.",
            memory_used=True,
            memory_grounded_findings=[
                "A prior active memory linked checkout latency to stale cache state."
            ],
            likely_root_cause="Worker-local cache state may be stale, but this is not confirmed.",
            recommended_next_steps=[
                "Check checkout worker cache freshness before restarting traffic."
            ],
            cautions=[
                "Confirm current telemetry before applying the previous resolution."
            ],
            memory_influence_notes=[
                "The checkout cache memory influenced the cache-freshness checks."
            ],
        )

    def recommend(
        self,
        incident: IncidentAnalysisInput,
        memories: list[RecalledMemoryResponse],
    ) -> MemoryAssistedRecommendationResult:
        if self._db_session is not None:
            self.in_transaction_during_call = self._db_session.in_transaction()
        self.calls.append((incident, memories))
        return MemoryAssistedRecommendationResult(
            model_id="fake-nova-model",
            payload=self._payload,
        )


def similar_memory(
    *,
    cosine_distance: float = 0.2,
    summary: str = "Checkout cache latency fixed by clearing stale cache",
    success_count: int = 2,
    failure_count: int = 0,
) -> SimilarMemoryRecord:
    return SimilarMemoryRecord(
        memory_id=UUID("00000000-0000-0000-0000-000000000101"),
        incident_id=UUID("00000000-0000-0000-0000-000000000201"),
        memory_incident_service="checkout-api",
        memory_type="resolution",
        summary=summary,
        root_cause="Worker-local cache entries drifted from shared cache.",
        resolution="Restart workers, clear stale cache, and warm critical keys.",
        embedding_model_id="fake-memory-model",
        embedding_dimension=1024,
        success_count=success_count,
        failure_count=failure_count,
        status="active",
        superseded_by=None,
        superseded_at=None,
        supersession_reason=None,
        cosine_distance=cosine_distance,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        replacement_memory_summary=None,
        replacement_memory_type=None,
        replacement_memory_status=None,
    )


def override_embedding_service(service: object) -> None:
    app.dependency_overrides[get_embedding_service_factory] = lambda: lambda: service


def override_recommendation_service(service: object) -> None:
    app.dependency_overrides[get_memory_assisted_recommendation_service_factory] = (
        lambda: lambda: service
    )


def override_memory_searcher(searcher: object) -> None:
    app.dependency_overrides[get_memory_recall_searcher] = lambda: searcher


def test_agent_recommendation_uses_recalled_memory_context(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    embedding_service = FakeEmbeddingService()
    recommendation_service = FakeRecommendationService(db_session=db_session)
    search_calls: list[tuple[tuple[float, ...], int]] = []

    def fake_searcher(
        session: Session,
        query_vector: tuple[float, ...],
        limit: int,
    ) -> list[SimilarMemoryRecord]:
        assert session is db_session
        search_calls.append((query_vector, limit))
        return [similar_memory()]

    override_embedding_service(embedding_service)
    override_recommendation_service(recommendation_service)
    override_memory_searcher(fake_searcher)

    response = client.post(f"/api/incidents/{incident['id']}/agent-recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == incident["id"]
    assert body["memory_used"] is True
    assert body["recalled_memory_count"] == 1
    assert body["model_id"] == "fake-nova-model"
    assert body["recalled_memories"] == [
        {
            "rank": 1,
            "memory_type": "resolution",
            "status": "active",
            "summary": "Checkout cache latency fixed by clearing stale cache",
            "root_cause": "Worker-local cache entries drifted from shared cache.",
            "resolution": "Restart workers, clear stale cache, and warm critical keys.",
            "success_count": 2,
            "failure_count": 0,
            "similarity": 0.8,
            "reliability": 0.75,
            "final_score": body["recalled_memories"][0]["final_score"],
            "why_recalled": (
                "Passed semantic gate with 0.80 similarity; "
                "reliability 0.75 from 2 successes and 0 failures; "
                "same service match contributed to final ranking."
            ),
        }
    ]
    assert body["recalled_memories"][0]["final_score"] == pytest.approx(0.81)
    assert "vector" not in response.text
    assert "embedding" not in response.text
    assert len(recommendation_service.calls) == 1
    incident_input, memories = recommendation_service.calls[0]
    assert incident_input.incident_id == UUID(incident["id"])
    assert memories[0].summary == "Checkout cache latency fixed by clearing stale cache"
    assert recommendation_service.in_transaction_during_call is False
    assert search_calls == [(embedding_service.vector, 20)]


def test_agent_recommendation_accepts_fenced_model_json(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)

    class FencedJsonBedrockClient:
        def converse(self, **kwargs: object) -> dict[str, object]:
            payload = {
                "summary": "Checkout latency resembles the recalled stale-cache memory.",
                "memory_used": True,
                "memory_grounded_findings": [
                    "The recalled checkout memory points to stale worker cache state."
                ],
                "likely_root_cause": "Worker-local cache state may be stale.",
                "recommended_next_steps": [
                    "Check cache freshness and clear stale worker-local state."
                ],
                "cautions": [
                    "Confirm current telemetry before applying the prior procedure."
                ],
                "memory_influence_notes": [
                    "The active checkout memory influenced the cache validation step."
                ],
            }
            return {
                "output": {
                    "message": {
                        "content": [
                            {"text": "```json\n" + json.dumps(payload) + "\n```"}
                        ]
                    }
                }
            }

    override_embedding_service(FakeEmbeddingService())
    override_recommendation_service(
        BedrockMemoryAssistedRecommendationService(
            FencedJsonBedrockClient(),
            "fake-nova-model",
        )
    )
    override_memory_searcher(lambda session, query_vector, limit: [similar_memory()])

    response = client.post(f"/api/incidents/{incident['id']}/agent-recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == (
        "Checkout latency resembles the recalled stale-cache memory."
    )
    assert body["memory_used"] is True
    assert body["recalled_memory_count"] == 1
    assert "vector" not in response.text
    assert "embedding" not in response.text


def test_agent_recommendation_handles_no_relevant_memories(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    no_memory_payload = ModelMemoryAssistedRecommendationPayload(
        summary="No relevant active memories were found for this incident.",
        memory_used=False,
        memory_grounded_findings=[
            "No relevant active memories passed the semantic gate."
        ],
        likely_root_cause="The likely root cause is unknown from current incident data.",
        recommended_next_steps=["Investigate from first principles using current telemetry."],
        cautions=["Do not assume the stale-cache pattern applies without evidence."],
        memory_influence_notes=[
            "No recalled memory influenced this recommendation."
        ],
    )
    recommendation_service = FakeRecommendationService(payload=no_memory_payload)
    override_embedding_service(FakeEmbeddingService())
    override_recommendation_service(recommendation_service)
    override_memory_searcher(lambda session, query_vector, limit: [])

    response = client.post(f"/api/incidents/{incident['id']}/agent-recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["memory_used"] is False
    assert body["recalled_memory_count"] == 0
    assert body["recalled_memories"] == []
    assert body["memory_grounded_findings"] == [
        "No relevant active memories passed the semantic gate."
    ]
    assert recommendation_service.calls[0][1] == []


def test_agent_recommendation_provider_failure_returns_safe_error(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    private_provider_detail = "fictional account and request identifiers"

    class FailedRecommendationService:
        def recommend(
            self,
            incident: IncidentAnalysisInput,
            memories: list[RecalledMemoryResponse],
        ) -> MemoryAssistedRecommendationResult:
            raise MemoryAssistedRecommendationServiceError(private_provider_detail)

    override_embedding_service(FakeEmbeddingService())
    override_recommendation_service(FailedRecommendationService())
    override_memory_searcher(lambda session, query_vector, limit: [similar_memory()])

    response = client.post(f"/api/incidents/{incident['id']}/agent-recommendation")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Memory-assisted recommendation is temporarily unavailable"
    }
    assert private_provider_detail not in response.text


def test_agent_recommendation_is_rate_limited(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RECALL_OPS_ENABLE_AI_RATE_LIMIT", "true")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    reset_ai_rate_limiter_for_tests()
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    override_recommendation_service(FakeRecommendationService())
    override_memory_searcher(lambda session, query_vector, limit: [])

    first_response = client.post(f"/api/incidents/{incident['id']}/agent-recommendation")
    limited_response = client.post(
        f"/api/incidents/{incident['id']}/agent-recommendation"
    )

    assert first_response.status_code == 200
    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "AI request rate limit exceeded. Please try again shortly."
    }


def test_agent_recommendation_returns_not_found_without_provider_calls(
    client: TestClient,
) -> None:
    embedding_service = FakeEmbeddingService()
    recommendation_service = FakeRecommendationService()
    override_embedding_service(embedding_service)
    override_recommendation_service(recommendation_service)
    override_memory_searcher(lambda session, query_vector, limit: [])

    response = client.post(
        "/api/incidents/00000000-0000-0000-0000-000000000001/agent-recommendation"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert embedding_service.inputs == []
    assert recommendation_service.calls == []


def test_agent_recommendation_rejects_invalid_uuid(client: TestClient) -> None:
    response = client.post("/api/incidents/not-a-uuid/agent-recommendation")

    assert response.status_code == 422
