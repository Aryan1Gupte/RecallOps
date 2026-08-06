"""Validation contracts for memory API payloads."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from recallops.services.memory_ranking import calculate_reliability


class MemoryType(StrEnum):
    RESOLUTION = "resolution"
    FAILED_ACTION = "failed_action"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class MemoryFeedbackOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class MemoryCreate(BaseModel):
    """Client-controlled fields accepted when creating a memory."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID | None = None
    memory_type: MemoryType
    summary: str = Field(max_length=4000)
    root_cause: str | None = Field(default=None, max_length=4000)
    resolution: str | None = Field(default=None, max_length=4000)

    @field_validator("memory_type", mode="before")
    @classmethod
    def strip_memory_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def strip_and_reject_blank_summary(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("must not be blank")
        return value

    @field_validator("root_cause", "resolution", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class MemoryResponse(BaseModel):
    """Public memory representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID | None
    memory_type: MemoryType
    summary: str
    root_cause: str | None
    resolution: str | None
    embedding_text: str
    embedding_model_id: str
    embedding_dimension: int
    success_count: int
    failure_count: int
    status: MemoryStatus
    superseded_by: UUID | None
    superseded_at: datetime | None
    supersession_reason: str | None
    created_at: datetime
    updated_at: datetime
    linked_incident_title: str | None = None
    linked_incident_service: str | None = None
    linked_incident_environment: str | None = None
    replacement_memory_summary: str | None = None
    replacement_memory_type: MemoryType | None = None
    replacement_memory_status: MemoryStatus | None = None

    @computed_field
    @property
    def reliability(self) -> float:
        return calculate_reliability(self.success_count, self.failure_count)


class MemoryFeedbackCreate(BaseModel):
    """Client-controlled memory feedback request."""

    model_config = ConfigDict(extra="forbid")

    outcome: MemoryFeedbackOutcome

    @field_validator("outcome", mode="before")
    @classmethod
    def strip_outcome(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class MemoryFeedbackResponse(BaseModel):
    """Public response after recording memory feedback."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: UUID
    outcome: MemoryFeedbackOutcome
    success_count: int
    failure_count: int
    reliability: float
    status: MemoryStatus
    updated_at: datetime
    message: str


class MemoryRejectCreate(BaseModel):
    """Client-controlled memory rejection request."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=4000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_optional_reason(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class MemoryRejectResponse(BaseModel):
    """Public response after rejecting a memory."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: UUID
    status: MemoryStatus
    supersession_reason: str | None
    updated_at: datetime
    message: str


class MemorySupersedeCreate(BaseModel):
    """Client-controlled memory supersession request."""

    model_config = ConfigDict(extra="forbid")

    superseded_by: UUID
    reason: str | None = Field(default=None, max_length=4000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_optional_reason(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class MemorySupersedeResponse(BaseModel):
    """Public response after superseding a memory."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: UUID
    status: MemoryStatus
    superseded_by: UUID | None
    superseded_at: datetime | None
    supersession_reason: str | None
    updated_at: datetime
    message: str


class RecalledMemoryResponse(BaseModel):
    """One memory returned from semantic recall without vector values."""

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    incident_id: UUID | None
    memory_type: MemoryType
    summary: str
    root_cause: str | None
    resolution: str | None
    status: MemoryStatus
    embedding_model_id: str
    embedding_dimension: int
    success_count: int
    failure_count: int
    superseded_by: UUID | None = None
    superseded_at: datetime | None = None
    supersession_reason: str | None = None
    cosine_distance: float
    similarity: float
    reliability: float
    same_service: bool
    same_service_score: float
    final_score: float
    rank: int
    why_recalled: str


class MemoryRecallResponse(BaseModel):
    """Semantic recall result for an incident query."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    query_embedding_model_id: str
    query_embedding_dimension: int
    min_similarity: float
    top_k: int
    memories: list[RecalledMemoryResponse]
    message: str
    ranking_formula: str
    candidate_count: int
    returned_count: int
