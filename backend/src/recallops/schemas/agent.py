"""Validated contracts for memory-assisted incident recommendations."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from recallops.schemas.analysis import NonBlankText
from recallops.schemas.memory import MemoryStatus, MemoryType, RecalledMemoryResponse


class ModelMemoryAssistedRecommendationPayload(BaseModel):
    """Strict JSON fields that must be supplied by the recommendation model."""

    model_config = ConfigDict(extra="forbid")

    summary: NonBlankText
    memory_used: StrictBool
    memory_grounded_findings: list[NonBlankText] = Field(default_factory=list)
    likely_root_cause: NonBlankText
    recommended_next_steps: list[NonBlankText] = Field(default_factory=list)
    cautions: list[NonBlankText] = Field(default_factory=list)
    memory_influence_notes: list[NonBlankText] = Field(default_factory=list)

    @field_validator(
        "memory_grounded_findings",
        "recommended_next_steps",
        "cautions",
        "memory_influence_notes",
    )
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        """Keep every displayed recommendation item meaningful after trimming."""

        if any(not value for value in values):
            raise ValueError("recommendation list items must not be blank")
        return values


class AgentRecalledMemoryResponse(BaseModel):
    """Compact recalled memory context used by the agent, without vector fields."""

    model_config = ConfigDict(extra="forbid")

    rank: int
    memory_type: MemoryType
    status: MemoryStatus
    summary: str
    root_cause: str | None
    resolution: str | None
    success_count: int
    failure_count: int
    similarity: float
    reliability: float
    final_score: float
    why_recalled: str

    @classmethod
    def from_recalled_memory(
        cls,
        memory: RecalledMemoryResponse,
    ) -> "AgentRecalledMemoryResponse":
        return cls(
            rank=memory.rank,
            memory_type=memory.memory_type,
            status=memory.status,
            summary=memory.summary,
            root_cause=memory.root_cause,
            resolution=memory.resolution,
            success_count=memory.success_count,
            failure_count=memory.failure_count,
            similarity=memory.similarity,
            reliability=memory.reliability,
            final_score=memory.final_score,
            why_recalled=memory.why_recalled,
        )


class MemoryAssistedRecommendationResponse(ModelMemoryAssistedRecommendationPayload):
    """Public memory-assisted recommendation returned to the frontend."""

    incident_id: UUID
    recalled_memory_count: int
    recalled_memories: list[AgentRecalledMemoryResponse]
    model_id: NonBlankText
