"""Strict parsing and validation for model-generated analysis JSON."""

import json

from pydantic import ValidationError

from recallops.schemas.analysis import ModelAnalysisPayload


class AnalysisResponseError(RuntimeError):
    """Safe error raised when a model response violates the analysis contract."""


def parse_analysis_payload(raw_text: str) -> ModelAnalysisPayload:
    """Parse one strict JSON object without returning raw model output on failure."""

    try:
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise AnalysisResponseError("AI analysis response was not a JSON object")
        return ModelAnalysisPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError):
        raise AnalysisResponseError("AI analysis response was invalid") from None
