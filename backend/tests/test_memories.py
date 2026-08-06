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
from recallops.main import app
from recallops.models.incident import Incident
from recallops.models.memory import Memory
from recallops.repositories.memories import search_similar_active_memories
from recallops.services.memories import (
    CreateMemoryCommand,
    MemoryFeedbackValidationError,
    create_memory,
    reject_memory,
    submit_memory_feedback,
    supersede_memory,
)
from recallops.services.memory_ranking import calculate_reliability


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
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(self, text: str) -> EmbeddingResult:
        self.inputs.append(text)
        return EmbeddingResult(
            vector=(0.0,) * 1024,
            dimension=1024,
            input_text_token_count=18,
            model_id="fake-titan-model",
        )


def override_embedding_service(service: object) -> None:
    app.dependency_overrides[get_embedding_service_factory] = lambda: lambda: service


def memory_payload(incident_id: str | None = None) -> dict[str, str]:
    payload = {
        "memory_type": "resolution",
        "summary": "Cache flush restored checkout",
        "root_cause": "Workers held stale cache entries",
        "resolution": "Restarted checkout workers",
    }
    if incident_id is not None:
        payload["incident_id"] = incident_id
    return payload


def test_create_memory_with_fake_embedding_service(client: TestClient) -> None:
    incident = create_test_incident(client)
    service = FakeEmbeddingService()
    override_embedding_service(service)

    response = client.post("/api/memories", json=memory_payload(incident["id"]))

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["incident_id"] == incident["id"]
    assert body["memory_type"] == "resolution"
    assert body["summary"] == "Cache flush restored checkout"
    assert body["embedding_model_id"] == "fake-titan-model"
    assert body["embedding_dimension"] == 1024
    assert body["success_count"] == 0
    assert body["failure_count"] == 0
    assert body["reliability"] == 0.5
    assert body["status"] == "active"
    assert "embedding" not in body
    assert "vector" not in body
    assert service.inputs == [
        "Memory Type: resolution\n"
        "Summary: Cache flush restored checkout\n"
        "Root Cause: Workers held stale cache entries\n"
        "Resolution: Restarted checkout workers\n"
        "Incident Title: Checkout latency\n"
        "Incident Service: checkout-api\n"
        "Incident Environment: production"
    ]


def test_create_memory_service_accepts_command(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    service = FakeEmbeddingService()

    memory = create_memory(
        db_session,
        CreateMemoryCommand(
            incident_id=UUID(incident["id"]),
            memory_type="procedure",
            summary="Restarting checkout workers clears stale local cache",
            root_cause=None,
            resolution="Use the checkout worker restart runbook",
        ),
        lambda: service,
    )

    assert memory.incident_id == UUID(incident["id"])
    assert memory.memory_type == "procedure"
    assert memory.summary == "Restarting checkout workers clears stale local cache"
    assert "embedding" not in memory.__dict__


def test_create_memory_rejects_missing_linked_incident(client: TestClient) -> None:
    service = FakeEmbeddingService()
    override_embedding_service(service)

    response = client.post(
        "/api/memories",
        json=memory_payload("00000000-0000-0000-0000-000000000001"),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}
    assert service.inputs == []
    assert client.get("/api/memories").json() == []


def test_create_memory_rejects_summary_that_repeats_linked_incident_title(
    client: TestClient,
) -> None:
    incident = create_test_incident(client, "Checkout latency")
    service = FakeEmbeddingService()
    override_embedding_service(service)
    payload = memory_payload(incident["id"])
    payload["summary"] = "  checkout LATENCY  "

    response = client.post("/api/memories", json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Memory summary must describe what to remember, not repeat the incident title"
    }
    assert service.inputs == []
    assert client.get("/api/memories").json() == []


def test_create_memory_handles_embedding_failure_safely(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    private_provider_detail = "fictional account and request identifiers"

    class FailedEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise EmbeddingServiceError(private_provider_detail)

    override_embedding_service(FailedEmbeddingService())

    response = client.post("/api/memories", json=memory_payload(incident["id"]))

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Memory embedding is temporarily unavailable"
    }
    assert private_provider_detail not in response.text
    assert client.get("/api/memories").json() == []


def test_list_memories(client: TestClient, db_session: Session) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    first = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    first_memory = db_session.get(Memory, UUID(first["id"]))
    assert first_memory is not None
    first_memory.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()
    second_payload = memory_payload(incident["id"])
    second_payload["summary"] = "Second memory"
    second = client.post("/api/memories", json=second_payload).json()

    response = client.get("/api/memories")

    assert response.status_code == 200
    assert [memory["id"] for memory in response.json()] == [
        second["id"],
        first["id"],
    ]


def test_list_memories_filtered_by_status(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    active_response = client.get("/api/memories", params={"status": "active"})
    rejected_response = client.get("/api/memories", params={"status": "rejected"})

    assert [memory["id"] for memory in active_response.json()] == [created["id"]]
    assert rejected_response.json() == []


def test_list_memories_filtered_by_memory_type(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    resolution = client.post(
        "/api/memories",
        json=memory_payload(incident["id"]),
    ).json()
    procedure_payload = memory_payload(incident["id"])
    procedure_payload["memory_type"] = "procedure"
    procedure = client.post("/api/memories", json=procedure_payload).json()

    response = client.get("/api/memories", params={"memory_type": "procedure"})

    assert response.status_code == 200
    assert [memory["id"] for memory in response.json()] == [procedure["id"]]
    assert resolution["id"] not in response.text


def test_list_memories_filtered_by_incident_id(client: TestClient) -> None:
    first_incident = create_test_incident(client, "First incident")
    second_incident = create_test_incident(client, "Second incident")
    override_embedding_service(FakeEmbeddingService())
    first_memory = client.post(
        "/api/memories",
        json=memory_payload(first_incident["id"]),
    ).json()
    client.post("/api/memories", json=memory_payload(second_incident["id"]))

    response = client.get(
        "/api/memories",
        params={"incident_id": first_incident["id"]},
    )

    assert response.status_code == 200
    assert [memory["id"] for memory in response.json()] == [first_memory["id"]]


def test_get_memory_by_id(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.get(f"/api/memories/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert response.json()["reliability"] == 0.5
    assert "embedding" not in response.json()


def test_get_memory_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/memories/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json() == {"detail": "Memory not found"}


def test_get_memory_rejects_invalid_uuid(client: TestClient) -> None:
    response = client.get("/api/memories/not-a-uuid")

    assert response.status_code == 422


def test_public_memory_responses_exclude_raw_vector(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"]))
    listed = client.get("/api/memories")

    assert "vector" not in created.text
    assert '"embedding":' not in created.text
    assert "vector" not in listed.text
    assert '"embedding":' not in listed.text


def test_memory_responses_include_linked_incident_metadata(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())

    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    listed = client.get("/api/memories").json()[0]
    retrieved = client.get(f"/api/memories/{created['id']}").json()

    for memory in (created, listed, retrieved):
        assert memory["linked_incident_title"] == "Checkout latency"
        assert memory["linked_incident_service"] == "checkout-api"
        assert memory["linked_incident_environment"] == "production"
        assert memory["replacement_memory_summary"] is None
        assert memory["replacement_memory_type"] is None
        assert memory["replacement_memory_status"] is None
        assert "vector" not in memory
        assert "embedding" not in memory


def test_superseded_memory_response_includes_replacement_metadata(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["memory_type"] = "procedure"
    replacement_payload["summary"] = "Use the newer checkout restart runbook"
    replacement = client.post("/api/memories", json=replacement_payload).json()

    supersede_response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={
            "superseded_by": replacement["id"],
            "reason": "Newer procedure is clearer.",
        },
    )
    listed = client.get(
        "/api/memories",
        params={"status": "superseded"},
    ).json()
    retrieved = client.get(f"/api/memories/{original['id']}").json()

    assert supersede_response.status_code == 200
    assert len(listed) == 1
    for memory in (listed[0], retrieved):
        assert memory["status"] == "superseded"
        assert memory["superseded_by"] == replacement["id"]
        assert memory["replacement_memory_summary"] == (
            "Use the newer checkout restart runbook"
        )
        assert memory["replacement_memory_type"] == "procedure"
        assert memory["replacement_memory_status"] == "active"
        assert "vector" not in memory
        assert "embedding" not in memory


def test_active_replacement_candidates_are_available_through_list_endpoint(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Active replacement candidate"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    client.post(
        f"/api/memories/{original['id']}/reject",
        json={"reason": "Disposable inactive memory."},
    )

    response = client.get("/api/memories", params={"status": "active"})

    assert response.status_code == 200
    assert [memory["id"] for memory in response.json()] == [replacement["id"]]
    assert response.json()[0]["summary"] == "Active replacement candidate"


def test_feedback_success_increments_success_count_and_reliability(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["memory_id"] == created["id"]
    assert body["outcome"] == "success"
    assert body["success_count"] == 1
    assert body["failure_count"] == 0
    assert body["reliability"] == calculate_reliability(1, 0)
    assert body["status"] == "active"
    assert body["message"] == "Memory marked successful."
    assert "vector" not in response.text
    assert '"embedding":' not in response.text


def test_feedback_failure_increments_failure_count_and_reliability(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "failure"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "failure"
    assert body["success_count"] == 0
    assert body["failure_count"] == 1
    assert body["reliability"] == calculate_reliability(0, 1)
    assert body["message"] == "Memory marked failed."


def test_feedback_updates_memory_response_reliability(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )
    listed = client.get("/api/memories").json()
    retrieved = client.get(f"/api/memories/{created['id']}").json()

    assert listed[0]["success_count"] == 1
    assert listed[0]["failure_count"] == 0
    assert listed[0]["reliability"] == calculate_reliability(1, 0)
    assert retrieved["reliability"] == calculate_reliability(1, 0)


def test_feedback_returns_not_found_for_missing_memory(client: TestClient) -> None:
    response = client.post(
        "/api/memories/00000000-0000-0000-0000-000000000001/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Memory not found"}


def test_feedback_rejects_invalid_outcome(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "maybe"},
    )

    assert response.status_code == 422


def test_feedback_service_validates_outcome(db_session: Session) -> None:
    with pytest.raises(MemoryFeedbackValidationError):
        submit_memory_feedback(
            db_session,
            UUID("00000000-0000-0000-0000-000000000001"),
            "maybe",
        )


@pytest.mark.parametrize("inactive_status", ["superseded", "rejected"])
def test_feedback_rejects_inactive_memory(
    client: TestClient,
    db_session: Session,
    inactive_status: str,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    memory = db_session.get(Memory, UUID(created["id"]))
    assert memory is not None
    memory.status = inactive_status
    db_session.commit()

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Feedback is only accepted for active memories"
    }


def test_feedback_does_not_call_embedding_service(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    class FailingEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise AssertionError("Feedback must not call embeddings")

    override_embedding_service(FailingEmbeddingService())

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 200


def test_reject_active_memory(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )

    response = client.post(
        f"/api/memories/{created['id']}/reject",
        json={"reason": "Too vague for future operators."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["memory_id"] == created["id"]
    assert body["status"] == "rejected"
    assert body["supersession_reason"] == "Too vague for future operators."
    assert body["message"] == "Memory rejected."
    assert "vector" not in response.text
    assert '"embedding":' not in response.text
    stored = db_session.get(Memory, UUID(created["id"]))
    assert stored is not None
    assert stored.status == "rejected"
    assert stored.success_count == 1
    assert stored.failure_count == 0


def test_reject_nonexistent_memory_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/memories/00000000-0000-0000-0000-000000000001/reject",
        json={"reason": "No such memory."},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Memory not found"}


def test_reject_already_rejected_memory_returns_current_state(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    first_response = client.post(
        f"/api/memories/{created['id']}/reject",
        json={"reason": "Incorrect."},
    )

    second_response = client.post(
        f"/api/memories/{created['id']}/reject",
        json={"reason": "Different reason should not rewrite history."},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    body = second_response.json()
    assert body["status"] == "rejected"
    assert body["supersession_reason"] == "Incorrect."


def test_reject_superseded_memory_returns_conflict(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Replacement memory"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    original_memory = db_session.get(Memory, UUID(original["id"]))
    assert original_memory is not None
    original_memory.status = "superseded"
    original_memory.superseded_by = UUID(replacement["id"])
    db_session.commit()

    response = client.post(
        f"/api/memories/{original['id']}/reject",
        json={"reason": "Trying wrong workflow."},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Superseded memories cannot be rejected in this workflow"
    }


def test_reject_does_not_call_embedding_service(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    class FailingEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise AssertionError("Reject must not call embeddings")

    override_embedding_service(FailingEmbeddingService())

    response = client.post(
        f"/api/memories/{created['id']}/reject",
        json={"reason": "Wrong memory."},
    )

    assert response.status_code == 200


def test_reject_service_does_not_require_embedding_factory(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    result = reject_memory(
        db_session,
        UUID(created["id"]),
        "No longer trusted.",
    )

    assert result.status == "rejected"
    assert result.supersession_reason == "No longer trusted."


def test_supersede_active_memory_with_active_replacement(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Newer checkout restart procedure"
    replacement = client.post("/api/memories", json=replacement_payload).json()

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={
            "superseded_by": replacement["id"],
            "reason": "Newer resolution replaced the old procedure.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["memory_id"] == original["id"]
    assert body["status"] == "superseded"
    assert body["superseded_by"] == replacement["id"]
    assert body["superseded_at"] is not None
    assert body["supersession_reason"] == "Newer resolution replaced the old procedure."
    assert body["message"] == "Memory superseded."
    assert "vector" not in response.text
    assert '"embedding":' not in response.text

    original_memory = db_session.get(Memory, UUID(original["id"]))
    replacement_memory = db_session.get(Memory, UUID(replacement["id"]))
    assert original_memory is not None
    assert replacement_memory is not None
    assert original_memory.status == "superseded"
    assert original_memory.superseded_by == UUID(replacement["id"])
    assert original_memory.superseded_at is not None
    assert replacement_memory.status == "active"
    assert replacement_memory.superseded_by is None


def test_supersede_nonexistent_original_returns_404(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    replacement = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        "/api/memories/00000000-0000-0000-0000-000000000001/supersede",
        json={"superseded_by": replacement["id"]},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Memory not found"}


def test_supersede_nonexistent_replacement_returns_404(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": "00000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Replacement memory not found"}


def test_memory_cannot_supersede_itself(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": original["id"]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Memory cannot supersede itself"}


@pytest.mark.parametrize("replacement_status", ["rejected", "superseded"])
def test_supersede_replacement_must_be_active(
    client: TestClient,
    db_session: Session,
    replacement_status: str,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = f"Inactive {replacement_status} memory"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    replacement_memory = db_session.get(Memory, UUID(replacement["id"]))
    assert replacement_memory is not None
    replacement_memory.status = replacement_status
    db_session.commit()

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": replacement["id"]},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Replacement memory must be active"}


def test_rejected_memory_cannot_be_superseded(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Active replacement"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    original_memory = db_session.get(Memory, UUID(original["id"]))
    assert original_memory is not None
    original_memory.status = "rejected"
    db_session.commit()

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": replacement["id"]},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Rejected memories cannot be superseded in this workflow"
    }


def test_already_superseded_memory_returns_current_state(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "First replacement"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    other_payload = memory_payload(incident["id"])
    other_payload["summary"] = "Second replacement"
    other_replacement = client.post("/api/memories", json=other_payload).json()
    first_response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": replacement["id"], "reason": "First reason."},
    )

    second_response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": other_replacement["id"], "reason": "Second reason."},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    body = second_response.json()
    assert body["status"] == "superseded"
    assert body["superseded_by"] == replacement["id"]
    assert body["supersession_reason"] == "First reason."
    replacement_memory = db_session.get(Memory, UUID(replacement["id"]))
    other_memory = db_session.get(Memory, UUID(other_replacement["id"]))
    assert replacement_memory is not None
    assert other_memory is not None
    assert replacement_memory.status == "active"
    assert other_memory.status == "active"


def test_supersede_does_not_call_embedding_service(client: TestClient) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Active replacement"
    replacement = client.post("/api/memories", json=replacement_payload).json()

    class FailingEmbeddingService:
        def embed(self, text: str) -> EmbeddingResult:
            raise AssertionError("Supersede must not call embeddings")

    override_embedding_service(FailingEmbeddingService())

    response = client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": replacement["id"]},
    )

    assert response.status_code == 200


def test_supersede_service_does_not_require_embedding_factory(
    client: TestClient,
    db_session: Session,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Active replacement"
    replacement = client.post("/api/memories", json=replacement_payload).json()

    result = supersede_memory(
        db_session,
        UUID(original["id"]),
        UUID(replacement["id"]),
        "Safer replacement.",
    )

    assert result.status == "superseded"
    assert result.superseded_by == UUID(replacement["id"])


def test_feedback_on_rejected_memory_after_lifecycle_returns_conflict(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    created = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    client.post(
        f"/api/memories/{created['id']}/reject",
        json={"reason": "Incorrect."},
    )

    response = client.post(
        f"/api/memories/{created['id']}/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Feedback is only accepted for active memories"
    }


def test_feedback_on_superseded_memory_after_lifecycle_returns_conflict(
    client: TestClient,
) -> None:
    incident = create_test_incident(client)
    override_embedding_service(FakeEmbeddingService())
    original = client.post("/api/memories", json=memory_payload(incident["id"])).json()
    replacement_payload = memory_payload(incident["id"])
    replacement_payload["summary"] = "Active replacement"
    replacement = client.post("/api/memories", json=replacement_payload).json()
    client.post(
        f"/api/memories/{original['id']}/supersede",
        json={"superseded_by": replacement["id"]},
    )

    response = client.post(
        f"/api/memories/{original['id']}/feedback",
        json={"outcome": "success"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Feedback is only accepted for active memories"
    }


def test_memory_vector_search_returns_linked_incident_service(
    db_session: Session,
) -> None:
    incident = Incident(
        title="Checkout latency",
        description="Requests are timing out for fictional shoppers.",
        service="checkout-api",
        environment="production",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    vector = (1.0,) + (0.0,) * 1023
    memory = Memory(
        incident_id=incident.id,
        memory_type="resolution",
        summary="Restart checkout workers",
        root_cause=None,
        resolution="Restarted checkout workers",
        embedding_text="Memory Type: resolution\nSummary: Restart checkout workers",
        embedding="[" + ",".join(str(value) for value in vector) + "]",
        embedding_model_id="fake-memory-model",
        embedding_dimension=1024,
    )
    db_session.add(memory)
    db_session.commit()

    results = search_similar_active_memories(db_session, vector, 20)

    assert len(results) == 1
    assert results[0].memory_incident_service == "checkout-api"
    assert results[0].created_at is not None
    assert "embedding" not in results[0].__dict__
