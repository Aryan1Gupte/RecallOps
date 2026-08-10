"""Amazon Bedrock implementations of incident recommendation interfaces."""

import logging
from functools import lru_cache
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from recallops.ai.bedrock_client import BedrockClientError, build_bedrock_runtime_client
from recallops.ai.parsing import (
    AnalysisResponseError,
    MemoryAssistedRecommendationResponseError,
    parse_analysis_payload,
    parse_memory_assisted_recommendation_payload,
)
from recallops.ai.prompts import (
    INCIDENT_ANALYSIS_SYSTEM_PROMPT,
    MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT,
    build_incident_analysis_prompt,
    build_memory_assisted_recommendation_prompt,
)
from recallops.ai.protocols import (
    IncidentAnalysisInput,
    IncidentAnalysisService,
    MemoryAssistedRecommendationResult,
    MemoryAssistedRecommendationService,
)
from recallops.config import get_settings
from recallops.schemas.analysis import IncidentAnalysisResponse
from recallops.schemas.memory import RecalledMemoryResponse

logger = logging.getLogger(__name__)


class AnalysisServiceError(RuntimeError):
    """Safe boundary error for Bedrock or response-shape failures."""


class MemoryAssistedRecommendationServiceError(RuntimeError):
    """Safe boundary error for Bedrock recommendation failures."""


class BedrockIncidentAnalysisService:
    """Generate structured incident analysis with Bedrock Runtime Converse."""

    def __init__(self, client: Any, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": INCIDENT_ANALYSIS_SYSTEM_PROMPT}],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"text": build_incident_analysis_prompt(incident)}
                        ],
                    }
                ],
                inferenceConfig={"maxTokens": 1200, "temperature": 0.1},
            )
        except (BotoCoreError, ClientError):
            raise AnalysisServiceError("Bedrock analysis request failed") from None

        try:
            raw_text = _extract_converse_text(response)
            payload = parse_analysis_payload(raw_text)
        except (KeyError, TypeError, AnalysisResponseError):
            raise AnalysisServiceError("Bedrock analysis response was invalid") from None

        return IncidentAnalysisResponse(
            incident_id=incident.incident_id,
            model_id=self._model_id,
            **payload.model_dump(),
        )


class BedrockMemoryAssistedRecommendationService:
    """Generate structured recommendations with bounded memory context."""

    def __init__(self, client: Any, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    def recommend(
        self,
        incident: IncidentAnalysisInput,
        memories: list[RecalledMemoryResponse],
    ) -> MemoryAssistedRecommendationResult:
        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": MEMORY_ASSISTED_RECOMMENDATION_SYSTEM_PROMPT}],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": build_memory_assisted_recommendation_prompt(
                                    incident,
                                    memories,
                                )
                            }
                        ],
                    }
                ],
                inferenceConfig={"maxTokens": 2400, "temperature": 0.1},
            )
        except (BotoCoreError, ClientError):
            raise MemoryAssistedRecommendationServiceError(
                "Bedrock recommendation request failed"
            ) from None

        try:
            raw_text = _extract_converse_text(response)
            payload = parse_memory_assisted_recommendation_payload(raw_text)
        except (
            KeyError,
            TypeError,
            AnalysisResponseError,
            MemoryAssistedRecommendationResponseError,
        ) as error:
            logger.warning("agent recommendation parse failed: %s", error)
            raise MemoryAssistedRecommendationServiceError(
                "Bedrock recommendation response was invalid"
            ) from None

        return MemoryAssistedRecommendationResult(
            model_id=self._model_id,
            payload=payload,
        )


@lru_cache
def build_incident_analysis_service() -> IncidentAnalysisService:
    """Build one lazy Bedrock client using the standard AWS credential chain."""

    bedrock_settings = get_settings().require_bedrock()
    try:
        client = build_bedrock_runtime_client(bedrock_settings.region)
    except BedrockClientError:
        raise AnalysisServiceError("Bedrock client configuration failed") from None
    return BedrockIncidentAnalysisService(client, bedrock_settings.model_id)


@lru_cache
def build_memory_assisted_recommendation_service() -> MemoryAssistedRecommendationService:
    """Build one lazy Bedrock recommendation provider."""

    bedrock_settings = get_settings().require_bedrock()
    try:
        client = build_bedrock_runtime_client(bedrock_settings.region)
    except BedrockClientError:
        raise MemoryAssistedRecommendationServiceError(
            "Bedrock client configuration failed"
        ) from None
    return BedrockMemoryAssistedRecommendationService(
        client,
        bedrock_settings.model_id,
    )


def _extract_converse_text(response: dict[str, Any]) -> str:
    content = response["output"]["message"]["content"]
    raw_text = "".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )
    if not raw_text:
        raise AnalysisResponseError("Bedrock response contained no text")
    return raw_text
