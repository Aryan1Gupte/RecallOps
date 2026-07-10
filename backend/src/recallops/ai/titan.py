"""Amazon Titan Text Embeddings V2 provider implementation."""

from functools import lru_cache
from typing import Any
import json

from botocore.exceptions import BotoCoreError, ClientError

from recallops.ai.bedrock_client import BedrockClientError, build_bedrock_runtime_client
from recallops.ai.embedding_protocols import (
    EMBEDDING_DIMENSIONS,
    EmbeddingInputError,
    EmbeddingResult,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from recallops.config import get_settings

# A preview is a convenience feature, not a critical path: fail faster and
# retry less than the chat-analysis client so a slow Bedrock call can't tie
# up FastAPI's shared worker thread pool for as long.
EMBEDDING_READ_TIMEOUT_SECONDS = 20
EMBEDDING_MAX_ATTEMPTS = 2


class BedrockTitanEmbeddingService:
    """Generate normalized float embeddings through Bedrock Runtime."""

    def __init__(self, client: Any, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    def embed(self, text: str) -> EmbeddingResult:
        input_text = text.strip()
        if not input_text:
            raise EmbeddingInputError("Embedding input text must not be empty")

        request_body = json.dumps(
            {
                "inputText": input_text,
                "dimensions": EMBEDDING_DIMENSIONS,
                "normalize": True,
                "embeddingTypes": ["float"],
            }
        )

        try:
            response = self._client.invoke_model(
                body=request_body,
                modelId=self._model_id,
                accept="application/json",
                contentType="application/json",
            )
            payload = json.loads(response["body"].read())
            raw_vector = payload["embedding"]
            token_count = payload["inputTextTokenCount"]

            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in raw_vector
            ):
                raise EmbeddingValidationError(
                    "Embedding provider returned a non-numeric vector"
                )
            if len(raw_vector) != EMBEDDING_DIMENSIONS:
                raise EmbeddingValidationError(
                    "Embedding provider returned an unexpected vector dimension"
                )
            if isinstance(token_count, bool) or not isinstance(token_count, int):
                raise EmbeddingValidationError(
                    "Embedding provider returned an invalid token count"
                )

            return EmbeddingResult(
                vector=tuple(float(value) for value in raw_vector),
                dimension=len(raw_vector),
                input_text_token_count=token_count,
                model_id=self._model_id,
            )
        except (BotoCoreError, ClientError):
            raise EmbeddingServiceError("Bedrock embedding request failed") from None
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            EmbeddingValidationError,
        ):
            raise EmbeddingServiceError("Bedrock embedding response was invalid") from None


@lru_cache
def build_embedding_service() -> BedrockTitanEmbeddingService:
    """Build one lazy Bedrock client using the standard AWS credential chain."""

    embedding_settings = get_settings().require_bedrock_embedding()
    try:
        client = build_bedrock_runtime_client(
            embedding_settings.region,
            read_timeout=EMBEDDING_READ_TIMEOUT_SECONDS,
            max_attempts=EMBEDDING_MAX_ATTEMPTS,
        )
    except BedrockClientError:
        raise EmbeddingServiceError("Bedrock embedding client failed") from None
    return BedrockTitanEmbeddingService(client, embedding_settings.model_id)
