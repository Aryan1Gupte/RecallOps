"""Validated contracts for incident AI analysis."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ModelAnalysisPayload(BaseModel):
    """Strict JSON fields that must be supplied by the model."""

    model_config = ConfigDict(extra="forbid")

    summary: NonBlankText
    likely_category: NonBlankText
    hypotheses: list[NonBlankText] = Field(min_length=1)
    recommended_next_steps: list[NonBlankText] = Field(min_length=1)
    cautions: list[NonBlankText]

    @field_validator("hypotheses", "recommended_next_steps", "cautions")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        """Keep every displayed analysis item meaningful after trimming."""

        if any(not value for value in values):
            raise ValueError("analysis list items must not be blank")
        return values


class IncidentAnalysisResponse(ModelAnalysisPayload):
    """Public, validated analysis returned to the frontend."""

    incident_id: UUID
    model_id: NonBlankText
