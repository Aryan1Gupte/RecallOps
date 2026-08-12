"""Strict parsing and validation for model-generated analysis JSON."""

import json
from collections.abc import Iterable

from pydantic import ValidationError

from recallops.schemas.agent import ModelMemoryAssistedRecommendationPayload
from recallops.schemas.analysis import ModelAnalysisPayload


class AnalysisResponseError(RuntimeError):
    """Safe error raised when a model response violates the analysis contract."""


class MemoryAssistedRecommendationResponseError(RuntimeError):
    """Safe error raised when a model recommendation violates its contract."""


def parse_analysis_payload(raw_text: str) -> ModelAnalysisPayload:
    """Parse one strict JSON object without returning raw model output on failure."""

    try:
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise AnalysisResponseError("AI analysis response was not a JSON object")
        return ModelAnalysisPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError):
        raise AnalysisResponseError("AI analysis response was invalid") from None


def parse_memory_assisted_recommendation_payload(
    raw_text: str,
) -> ModelMemoryAssistedRecommendationPayload:
    """Parse one strict recommendation JSON object without returning raw output."""

    try:
        parsed = _loads_json_object_from_model_text(raw_text)
        if not isinstance(parsed, dict):
            raise MemoryAssistedRecommendationResponseError(
                "AI recommendation response was not a JSON object"
            )
        return ModelMemoryAssistedRecommendationPayload.model_validate(parsed)
    except json.JSONDecodeError:
        raise MemoryAssistedRecommendationResponseError(
            "AI recommendation response contained malformed JSON"
        ) from None
    except ValidationError as error:
        raise MemoryAssistedRecommendationResponseError(
            _validation_error_reason(error)
        ) from None


def _loads_json_object_from_model_text(raw_text: str) -> object:
    """Load exactly one JSON object, tolerating fences or harmless text."""

    stripped = raw_text.strip()
    if not stripped:
        raise json.JSONDecodeError("empty response", raw_text, 0)

    candidate = _strip_markdown_fence(stripped)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        object_text = _extract_single_json_object(candidate)
        if object_text is None:
            raise json.JSONDecodeError("no JSON object found", raw_text, 0) from None
        return json.loads(object_text)


def _strip_markdown_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```"):
        closing_line_index = _first_closing_fence_index(lines[1:])
        if closing_line_index is not None:
            trailing_text = "\n".join(lines[closing_line_index + 1 :]).strip()
            fenced_text = "\n".join(lines[1:closing_line_index]).strip()
            if "{" not in trailing_text and "}" not in trailing_text:
                return fenced_text
    return text


def _first_closing_fence_index(lines_after_opening: Iterable[str]) -> int | None:
    for offset, line in enumerate(lines_after_opening, start=1):
        if line.strip() == "```":
            return offset
    return None


def _extract_single_json_object(text: str) -> str | None:
    spans = _json_object_spans(text)
    if len(spans) != 1:
        return None

    start, end = spans[0]
    outside_text = text[:start] + text[end:]
    if "{" in outside_text or "}" in outside_text:
        return None
    return text[start:end]


def _json_object_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if depth == 0:
            if char == "{":
                start = index
                depth = 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                if start is not None:
                    spans.append((start, index + 1))
                start = None

    return spans


def _validation_error_reason(error: ValidationError) -> str:
    first_error = error.errors(include_context=False, include_input=False)[0]
    location = ".".join(str(part) for part in first_error.get("loc", ())) or "response"
    error_type = str(first_error.get("type", "invalid"))
    if error_type == "missing":
        return f"AI recommendation response was missing field {location}"
    if error_type == "extra_forbidden":
        return f"AI recommendation response contained unexpected field {location}"
    return f"AI recommendation response field {location} was invalid"
