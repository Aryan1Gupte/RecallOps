"""Amazon Bedrock implementation of the incident analysis interface."""

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from recallops.ai.parsing import AnalysisResponseError, parse_analysis_payload
from recallops.ai.prompts import (
    INCIDENT_ANALYSIS_SYSTEM_PROMPT,
    build_incident_analysis_prompt,
)
from recallops.ai.protocols import IncidentAnalysisInput, IncidentAnalysisService
from recallops.config import get_settings
from recallops.schemas.analysis import IncidentAnalysisResponse


class AnalysisServiceError(RuntimeError):
    """Safe boundary error for Bedrock or response-shape failures."""


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
            content = response["output"]["message"]["content"]
            raw_text = "".join(
                block["text"]
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
            if not raw_text:
                raise AnalysisResponseError("AI analysis response contained no text")
            payload = parse_analysis_payload(raw_text)
        except (KeyError, TypeError, AnalysisResponseError):
            raise AnalysisServiceError("Bedrock analysis response was invalid") from None

        return IncidentAnalysisResponse(
            incident_id=incident.incident_id,
            model_id=self._model_id,
            **payload.model_dump(),
        )


@lru_cache
def build_incident_analysis_service() -> IncidentAnalysisService:
    """Build one lazy Bedrock client using the standard AWS credential chain."""

    bedrock_settings = get_settings().require_bedrock()
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=bedrock_settings.region,
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={"mode": "standard", "total_max_attempts": 3},
            ),
        )
    except BotoCoreError:
        raise AnalysisServiceError("Bedrock client configuration failed") from None
    return BedrockIncidentAnalysisService(client, bedrock_settings.model_id)
