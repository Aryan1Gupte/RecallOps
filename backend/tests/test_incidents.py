from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from recallops.models.incident import Incident


def incident_payload(title: str = "Checkout latency") -> dict[str, str]:
    return {
        "title": title,
        "description": "Requests are timing out for fictional shoppers.",
        "service": "checkout-api",
        "environment": "production",
    }


def test_create_incident(client: TestClient) -> None:
    response = client.post("/api/incidents", json=incident_payload())

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["title"] == "Checkout latency"
    assert body["status"] == "open"
    assert body["created_at"]
    assert body["updated_at"]


def test_list_incidents_newest_first(
    client: TestClient,
    db_session: Session,
) -> None:
    first_response = client.post(
        "/api/incidents",
        json=incident_payload("Earlier incident"),
    )
    first = db_session.get(Incident, UUID(first_response.json()["id"]))
    assert first is not None
    first.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    client.post("/api/incidents", json=incident_payload("Newest incident"))
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert [incident["title"] for incident in response.json()] == [
        "Newest incident",
        "Earlier incident",
    ]


def test_list_incidents_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == []


def test_retrieve_incident_by_id(client: TestClient) -> None:
    created = client.post("/api/incidents", json=incident_payload()).json()

    response = client.get(f"/api/incidents/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_retrieve_incident_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/incidents/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


def test_retrieve_incident_rejects_invalid_uuid(client: TestClient) -> None:
    response = client.get("/api/incidents/not-a-uuid")

    assert response.status_code == 422
