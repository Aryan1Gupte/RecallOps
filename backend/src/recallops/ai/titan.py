"""Amazon Titan Text Embeddings V2 provider implementation."""

from functools import lru_cache
from typing import Any
import json

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from recallops.ai.embedding_protocols import (
    EmbeddingInputError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingServiceError,
    EmbeddingValidationError,
)
from recallops.config import get_settings

TITAN_EMBEDDING_DIMENSIONS = 1024


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
                "dimensions": TITAN_EMBEDDING_DIMENSIONS,
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

            if not isinstance(raw_vector, list) or not raw_vector:
                raise EmbeddingValidationError(
                    "Embedding provider returned an empty vector"
                )
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in raw_vector
            ):
                raise EmbeddingValidationError(
                    "Embedding provider returned a non-numeric vector"
                )
            if isinstance(token_count, bool) or not isinstance(token_count, int):
                raise EmbeddingValidationError(
                    "Embedding provider returned an invalid token count"
                )

            return EmbeddingResult(
                vector=tuple(float(value) for value in raw_vector),
                dimension=TITAN_EMBEDDING_DIMENSIONS,
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
def build_embedding_service() -> EmbeddingService:
    """Build one lazy Bedrock client using the standard AWS credential chain."""

    embedding_settings = get_settings().require_bedrock_embedding()
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=embedding_settings.region,
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={"mode": "standard", "total_max_attempts": 3},
            ),
        )
    except BotoCoreError:
        raise EmbeddingServiceError("Bedrock embedding client failed") from None
    return BedrockTitanEmbeddingService(client, embedding_settings.model_id)
