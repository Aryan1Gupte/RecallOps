import json
from uuid import uuid4

import pytest

from recallops.ai.bedrock import (
    BedrockMemoryAssistedRecommendationService,
    MemoryAssistedRecommendationServiceError,
)
from recallops.ai.parsing import (
    MemoryAssistedRecommendationResponseError,
    parse_memory_assisted_recommendation_payload,
)
from recallops.ai.prompts import (
    MAX_RECOMMENDATION_PROMPT_MEMORIES,
    MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT,
    build_memory_assisted_recommendation_prompt,
)
from recallops.ai.protocols import IncidentAnalysisInput
from recallops.schemas.memory import RecalledMemoryResponse


VALID_RECOMMENDATION = {
    "summary": "Checkout latency resembles prior stale-cache incidents.",
    "memory_used": True,
    "memory_grounded_findings": [
        "A reliable checkout memory links this symptom to stale cache state."
    ],
    "likely_root_cause": "Worker-local cache state may be stale, but it is not confirmed.",
    "recommended_next_steps": ["Check cache freshness before changing traffic."],
    "cautions": ["Confirm current telemetry before applying previous fixes."],
    "memory_influence_notes": [
        "The checkout memory influenced the cache-freshness recommendation."
    ],
}


def incident_input() -> IncidentAnalysisInput:
    return IncidentAnalysisInput(
        incident_id=uuid4(),
        title="Checkout latency recurrence",
        description="Checkout requests are timing out again.",
        service="checkout-api",
        environment="production",
        status="open",
    )


def recalled_memory() -> RecalledMemoryResponse:
    return RecalledMemoryResponse(
        memory_id=uuid4(),
        incident_id=uuid4(),
        memory_type="resolution",
        summary="Checkout cache latency fixed by clearing stale cache",
        root_cause="Worker-local cache drift.",
        resolution="Restart workers, clear stale cache, and warm keys.",
        status="active",
        embedding_model_id="fake-memory-model",
        embedding_dimension=1024,
        success_count=2,
        failure_count=0,
        superseded_by=None,
        superseded_at=None,
        supersession_reason=None,
        cosine_distance=0.2,
        similarity=0.8,
        reliability=0.75,
        same_service=True,
        same_service_score=1.0,
        final_score=0.81,
        rank=1,
        why_recalled="Passed semantic gate with 0.80 similarity.",
        replacement_memory_summary=None,
        replacement_memory_type=None,
        replacement_memory_status=None,
    )


def test_parse_memory_assisted_recommendation_payload_validates_plain_json() -> None:
    payload = parse_memory_assisted_recommendation_payload(
        json.dumps(VALID_RECOMMENDATION)
    )

    assert payload.summary == VALID_RECOMMENDATION["summary"]
    assert payload.memory_used is True
    assert payload.recommended_next_steps == VALID_RECOMMENDATION[
        "recommended_next_steps"
    ]


@pytest.mark.parametrize(
    "raw_response",
    [
        "```json\n" + json.dumps(VALID_RECOMMENDATION) + "\n```",
        "Here is the JSON:\n" + json.dumps(VALID_RECOMMENDATION),
        json.dumps(VALID_RECOMMENDATION) + "\nThis is the recommendation.",
    ],
)
def test_parse_memory_assisted_recommendation_payload_extracts_json_object(
    raw_response: str,
) -> None:
    payload = parse_memory_assisted_recommendation_payload(raw_response)

    assert payload.summary == VALID_RECOMMENDATION["summary"]
    assert payload.memory_used is True


def test_parse_memory_assisted_recommendation_payload_defaults_optional_lists() -> None:
    payload = parse_memory_assisted_recommendation_payload(
        json.dumps(
            {
                "summary": "Use current telemetry before applying memory.",
                "memory_used": True,
                "likely_root_cause": "Cache drift is possible but not confirmed.",
            }
        )
    )

    assert payload.memory_grounded_findings == []
    assert payload.recommended_next_steps == []
    assert payload.cautions == []
    assert payload.memory_influence_notes == []


@pytest.mark.parametrize(
    "raw_response",
    [
        "not json",
        json.dumps({"summary": "Missing required fields"}),
        json.dumps({**VALID_RECOMMENDATION, "unexpected": "field"}),
        json.dumps({**VALID_RECOMMENDATION, "memory_used": "yes"}),
    ],
)
def test_parse_memory_assisted_recommendation_payload_rejects_invalid_output(
    raw_response: str,
) -> None:
    with pytest.raises(MemoryAssistedRecommendationResponseError):
        parse_memory_assisted_recommendation_payload(raw_response)


def test_memory_assisted_prompt_includes_memory_context_without_ids_or_vectors() -> None:
    prompt = build_memory_assisted_recommendation_prompt(
        incident_input(),
        [recalled_memory()],
    )

    assert "Checkout latency recurrence" in prompt
    assert "Checkout cache latency fixed by clearing stale cache" in prompt
    assert "\"reliability\":0.75" in prompt
    assert "memory_id" not in prompt
    assert "incident_id" not in prompt
    assert "embedding" not in prompt
    assert "vector" not in prompt


def test_memory_assisted_prompt_uses_exact_output_contract() -> None:
    assert "Return only one JSON object" in MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT
    assert "Do not use Markdown" in MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT
    for field_name in (
        "summary",
        "memory_used",
        "memory_grounded_findings",
        "likely_root_cause",
        "recommended_next_steps",
        "cautions",
        "memory_influence_notes",
    ):
        assert field_name in MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT


def test_memory_assisted_prompt_limits_memory_context() -> None:
    prompt = build_memory_assisted_recommendation_prompt(
        incident_input(),
        [recalled_memory() for _ in range(MAX_RECOMMENDATION_PROMPT_MEMORIES + 2)],
    )

    assert prompt.count("Checkout cache latency fixed by clearing stale cache") == (
        MAX_RECOMMENDATION_PROMPT_MEMORIES
    )


def test_bedrock_memory_assisted_service_uses_converse_and_validates_response() -> None:
    class FakeBedrockClient:
        request: dict[str, object] | None = None

        def converse(self, **kwargs: object) -> dict[str, object]:
            self.request = kwargs
            return {
                "output": {
                    "message": {
                        "content": [{"text": json.dumps(VALID_RECOMMENDATION)}]
                    }
                }
            }

    client = FakeBedrockClient()
    service = BedrockMemoryAssistedRecommendationService(client, "fake-model-id")

    result = service.recommend(incident_input(), [recalled_memory()])

    assert result.model_id == "fake-model-id"
    assert result.payload.summary == VALID_RECOMMENDATION["summary"]
    assert client.request is not None
    assert client.request["modelId"] == "fake-model-id"
    assert "Checkout cache latency fixed by clearing stale cache" in str(
        client.request["messages"]
    )


def test_bedrock_memory_assisted_service_rejects_invalid_json_safely() -> None:
    class InvalidResponseClient:
        def converse(self, **kwargs: object) -> dict[str, object]:
            return {
                "output": {"message": {"content": [{"text": "private raw output"}]}}
            }

    service = BedrockMemoryAssistedRecommendationService(
        InvalidResponseClient(),
        "fake-model-id",
    )

    with pytest.raises(
        MemoryAssistedRecommendationServiceError,
        match="Bedrock recommendation response was invalid",
    ) as error:
        service.recommend(incident_input(), [recalled_memory()])

    assert "private raw output" not in str(error.value)
