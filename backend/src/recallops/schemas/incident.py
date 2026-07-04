"""Validation contracts for incident API payloads."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class IncidentEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    UAT = "uat"
    PRODUCTION = "production"


class IncidentCreate(BaseModel):
    """Client-controlled fields accepted when creating an incident."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=200)
    description: str
    service: str = Field(max_length=100)
    environment: IncidentEnvironment
    status: IncidentStatus = IncidentStatus.OPEN

    @field_validator(
        "title",
        "description",
        "service",
        "environment",
        "status",
        mode="before",
    )
    @classmethod
    def strip_and_reject_blank_text(cls, value: object) -> object:
        """Normalize client text before enum and length validation."""

        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("must not be blank")
        return value


class IncidentResponse(BaseModel):
    """Public incident representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    service: str
    environment: IncidentEnvironment
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
