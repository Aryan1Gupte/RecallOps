import json
from uuid import uuid4

import pytest

from recallops.ai.bedrock import (
    AnalysisServiceError,
    BedrockIncidentAnalysisService,
)
from recallops.ai.parsing import AnalysisResponseError, parse_analysis_payload
from recallops.ai.protocols import IncidentAnalysisInput


VALID_ANALYSIS = {
    "summary": "The service is returning fictional elevated latency.",
    "likely_category": "service latency",
    "hypotheses": ["A downstream call may be slow."],
    "recommended_next_steps": ["Inspect downstream latency metrics."],
    "cautions": ["Do not treat the hypothesis as confirmed."],
}


def test_parse_analysis_payload_validates_strict_json() -> None:
    payload = parse_analysis_payload(json.dumps(VALID_ANALYSIS))

    assert payload.summary == VALID_ANALYSIS["summary"]
    assert payload.hypotheses == VALID_ANALYSIS["hypotheses"]


@pytest.mark.parametrize(
    "raw_response",
    [
        "not json",
        json.dumps({"summary": "Missing required fields"}),
        json.dumps({**VALID_ANALYSIS, "unexpected": "field"}),
    ],
)
def test_parse_analysis_payload_rejects_invalid_model_output(
    raw_response: str,
) -> None:
    with pytest.raises(AnalysisResponseError):
        parse_analysis_payload(raw_response)


def test_bedrock_service_uses_converse_and_validates_response() -> None:
    class FakeBedrockClient:
        request: dict[str, object] | None = None

        def converse(self, **kwargs: object) -> dict[str, object]:
            self.request = kwargs
            return {
                "output": {
                    "message": {
                        "content": [{"text": json.dumps(VALID_ANALYSIS)}]
                    }
                }
            }

    client = FakeBedrockClient()
    service = BedrockIncidentAnalysisService(client, "fake-model-id")
    incident_id = uuid4()

    result = service.analyze(
        IncidentAnalysisInput(
            incident_id=incident_id,
            title="Fictional latency",
            description="Example requests are slow.",
            service="checkout-api",
            environment="test",
            status="open",
        )
    )

    assert result.incident_id == incident_id
    assert result.model_id == "fake-model-id"
    assert client.request is not None
    assert client.request["modelId"] == "fake-model-id"


def test_bedrock_service_rejects_invalid_json_without_exposing_it() -> None:
    class InvalidResponseClient:
        def converse(self, **kwargs: object) -> dict[str, object]:
            return {
                "output": {"message": {"content": [{"text": "private raw output"}]}}
            }

    service = BedrockIncidentAnalysisService(
        InvalidResponseClient(),
        "fake-model-id",
    )

    with pytest.raises(
        AnalysisServiceError,
        match="Bedrock analysis response was invalid",
    ) as error:
        service.analyze(
            IncidentAnalysisInput(
                incident_id=uuid4(),
                title="Fictional incident",
                description="Example description.",
                service="example-service",
                environment="test",
                status="open",
            )
        )

    assert "private raw output" not in str(error.value)
