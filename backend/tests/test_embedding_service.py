import json
from pathlib import Path

import pytest

from recallops.ai.embedding_protocols import (
    EMBEDDING_DIMENSIONS,
    EmbeddingInputError,
    EmbeddingResult,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from recallops.ai.titan import BedrockTitanEmbeddingService


class FakeResponseBody:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_titan_service_requests_normalized_1024_dimension_embedding() -> None:
    class FakeBedrockClient:
        request: dict[str, object] | None = None

        def invoke_model(self, **kwargs: object) -> dict[str, object]:
            self.request = kwargs
            return {
                "body": FakeResponseBody(
                    {
                        "embedding": [0.0] * EMBEDDING_DIMENSIONS,
                        "inputTextTokenCount": 12,
                    }
                )
            }

    client = FakeBedrockClient()
    service = BedrockTitanEmbeddingService(client, "fake-titan-model")

    result = service.embed("Fictional incident text")

    assert result.dimension == EMBEDDING_DIMENSIONS
    assert len(result.vector) == EMBEDDING_DIMENSIONS
    assert result.input_text_token_count == 12
    assert client.request is not None
    request_body = json.loads(str(client.request["body"]))
    assert request_body == {
        "inputText": "Fictional incident text",
        "dimensions": 1024,
        "normalize": True,
        "embeddingTypes": ["float"],
    }


def test_titan_service_rejects_empty_input() -> None:
    service = BedrockTitanEmbeddingService(object(), "fake-titan-model")

    with pytest.raises(EmbeddingInputError):
        service.embed("   ")


def test_titan_service_rejects_unexpected_vector_dimension() -> None:
    class ShortVectorBedrockClient:
        def invoke_model(self, **kwargs: object) -> dict[str, object]:
            return {
                "body": FakeResponseBody(
                    {
                        "embedding": [0.0] * (EMBEDDING_DIMENSIONS - 1),
                        "inputTextTokenCount": 12,
                    }
                )
            }

    service = BedrockTitanEmbeddingService(
        ShortVectorBedrockClient(), "fake-titan-model"
    )

    with pytest.raises(EmbeddingServiceError):
        service.embed("Fictional incident text")


def test_embedding_result_rejects_empty_vector() -> None:
    with pytest.raises(EmbeddingValidationError, match="must not be empty"):
        EmbeddingResult(
            vector=(),
            dimension=0,
            input_text_token_count=1,
            model_id="fake-titan-model",
        )


def test_embedding_result_rejects_dimension_mismatch() -> None:
    with pytest.raises(EmbeddingValidationError, match="equal vector length"):
        EmbeddingResult(
            vector=(0.1, 0.2),
            dimension=1024,
            input_text_token_count=1,
            model_id="fake-titan-model",
        )


def test_memory_services_use_shared_embedding_protocol() -> None:
    source_root = Path(__file__).parents[1] / "src" / "recallops" / "services"
    for path in (
        source_root / "memories.py",
        source_root / "memory_recall.py",
    ):
        assert "class EmbeddingService(Protocol)" not in path.read_text()
