from fastapi.testclient import TestClient

from recallops.ai.dependencies import get_incident_analysis_service_factory
from recallops.ai.protocols import IncidentAnalysisInput
from recallops.api.rate_limit import (
    FixedWindowRateLimiter,
    reset_ai_rate_limiter_for_tests,
)
from recallops.config import get_settings
from recallops.main import app
from recallops.schemas.analysis import IncidentAnalysisResponse


class FakeAnalysisService:
    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        return IncidentAnalysisResponse(
            incident_id=incident.incident_id,
            summary="The fictional incident has a safe analysis.",
            likely_category="service latency",
            hypotheses=["A dependency may be slow."],
            recommended_next_steps=["Check dependency latency."],
            cautions=["Use operational telemetry before acting."],
            model_id="fake-analysis-model",
        )


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


def test_fixed_window_rate_limiter_resets_after_window() -> None:
    now = 0.0
    limiter = FixedWindowRateLimiter(
        max_requests=1,
        window_seconds=10,
        clock=lambda: now,
    )

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False

    now = 10.0
    assert limiter.allow("client-a") is True


def test_fixed_window_rate_limiter_evicts_stale_buckets() -> None:
    now = 0.0
    limiter = FixedWindowRateLimiter(
        max_requests=1,
        window_seconds=10,
        clock=lambda: now,
    )

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.bucket_count == 2

    now = 10.0
    assert limiter.allow("client-c") is True
    assert limiter.bucket_count == 1


def test_fixed_window_rate_limiter_bounds_bucket_count() -> None:
    limiter = FixedWindowRateLimiter(
        max_requests=1,
        window_seconds=60,
        max_buckets=2,
        clock=lambda: 0.0,
    )

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.allow("client-c") is True

    assert limiter.bucket_count == 2


def test_paid_ai_endpoint_rate_limited_and_health_is_not(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RECALL_OPS_ENABLE_AI_RATE_LIMIT", "true")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    reset_ai_rate_limiter_for_tests()
    incident = create_test_incident(client)
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    first_response = client.post(f"/api/incidents/{incident['id']}/analysis")
    limited_response = client.post(f"/api/incidents/{incident['id']}/analysis")
    health_response = client.get("/api/health")

    assert first_response.status_code == 200
    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "AI request rate limit exceeded. Please try again shortly."
    }
    assert health_response.status_code == 200


def test_spoofed_forwarded_for_does_not_bypass_limiter_by_default(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RECALL_OPS_ENABLE_AI_RATE_LIMIT", "true")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RECALL_OPS_AI_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.delenv("RECALL_OPS_TRUST_PROXY_HEADERS", raising=False)
    get_settings.cache_clear()
    reset_ai_rate_limiter_for_tests()
    incident = create_test_incident(client)
    app.dependency_overrides[get_incident_analysis_service_factory] = (
        lambda: lambda: FakeAnalysisService()
    )

    first_response = client.post(
        f"/api/incidents/{incident['id']}/analysis",
        headers={"x-forwarded-for": "198.51.100.10"},
    )
    spoofed_response = client.post(
        f"/api/incidents/{incident['id']}/analysis",
        headers={"x-forwarded-for": "198.51.100.11"},
    )

    assert first_response.status_code == 200
    assert spoofed_response.status_code == 429
