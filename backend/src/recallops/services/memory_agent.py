"""Bounded memory-assisted incident recommendation service."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from recallops.ai.bedrock import MemoryAssistedRecommendationServiceError
from recallops.ai.embedding_protocols import EmbeddingService
from recallops.ai.protocols import (
    MemoryAssistedRecommendationService,
    build_incident_analysis_input,
)
from recallops.config import BedrockConfigurationError
from recallops.repositories.incidents import get_incident
from recallops.repositories.memories import search_similar_active_memories
from recallops.schemas.agent import (
    AgentRecalledMemoryResponse,
    MemoryAssistedRecommendationResponse,
)
from recallops.schemas.memory import MemoryRecallResponse
from recallops.services.memory_recall import (
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_RECALL_TOP_K,
    IncidentForRecallNotFoundError,
    MemoryRecallEmbeddingConfigurationUnavailableError,
    MemoryRecallEmbeddingUnavailableError,
    MemoryRecallResultValidationError,
    MemoryRecallSearcher,
    recall_similar_memories_for_incident,
)

MAX_AGENT_RECALLED_MEMORIES = 3
DEFAULT_AGENT_RECALLED_MEMORIES = min(MAX_AGENT_RECALLED_MEMORIES, DEFAULT_RECALL_TOP_K)
EmbeddingServiceFactory = Callable[[], EmbeddingService]
MemoryAssistedRecommendationServiceFactory = Callable[
    [],
    MemoryAssistedRecommendationService,
]


class IncidentForAgentNotFoundError(RuntimeError):
    """Raised when the agent target incident does not exist."""


class MemoryAgentEmbeddingConfigurationUnavailableError(RuntimeError):
    """Raised when agent recall embedding settings are incomplete."""


class MemoryAgentEmbeddingUnavailableError(RuntimeError):
    """Raised when agent recall embedding generation fails."""


class MemoryAgentRecallUnavailableError(RuntimeError):
    """Raised when memory recall cannot safely produce ranked context."""


class MemoryAgentRecommendationConfigurationUnavailableError(RuntimeError):
    """Raised when Bedrock recommendation settings are incomplete."""


class MemoryAgentRecommendationUnavailableError(RuntimeError):
    """Raised when Bedrock cannot produce a safe recommendation."""


def build_memory_assisted_recommendation(
    session: Session,
    incident_id: UUID,
    *,
    embedding_service_factory: EmbeddingServiceFactory,
    recommendation_service_factory: MemoryAssistedRecommendationServiceFactory,
    searcher: MemoryRecallSearcher = search_similar_active_memories,
    memory_limit: int = DEFAULT_AGENT_RECALLED_MEMORIES,
) -> MemoryAssistedRecommendationResponse:
    """Create one bounded recommendation using recalled active memories."""

    incident = get_incident(session, incident_id)
    if incident is None:
        raise IncidentForAgentNotFoundError("Incident not found")

    incident_input = build_incident_analysis_input(incident)
    # The incident DTO is copied, so the initial read transaction can end
    # before the slower Titan recall embedding request.
    session.rollback()

    recall_response = _recall_agent_memories(
        session,
        incident_input.incident_id,
        embedding_service_factory=embedding_service_factory,
        searcher=searcher,
        memory_limit=memory_limit,
    )
    recalled_memories = recall_response.memories[: _bounded_memory_limit(memory_limit)]

    # Recall performs a DB vector search after embedding. End that read
    # transaction before the Bedrock recommendation request.
    session.rollback()

    try:
        recommendation_service = recommendation_service_factory()
        recommendation = recommendation_service.recommend(
            incident_input,
            recalled_memories,
        )
    except BedrockConfigurationError:
        raise MemoryAgentRecommendationConfigurationUnavailableError(
            "Memory-assisted recommendation is not configured"
        ) from None
    except MemoryAssistedRecommendationServiceError:
        raise MemoryAgentRecommendationUnavailableError(
            "Memory-assisted recommendation failed"
        ) from None

    agent_memory_context = [
        AgentRecalledMemoryResponse.from_recalled_memory(memory)
        for memory in recalled_memories
    ]
    payload = recommendation.payload
    return MemoryAssistedRecommendationResponse(
        incident_id=incident_input.incident_id,
        summary=payload.summary,
        memory_used=bool(agent_memory_context),
        recalled_memory_count=len(agent_memory_context),
        memory_grounded_findings=payload.memory_grounded_findings,
        likely_root_cause=payload.likely_root_cause,
        recommended_next_steps=payload.recommended_next_steps,
        cautions=payload.cautions,
        memory_influence_notes=payload.memory_influence_notes,
        recalled_memories=agent_memory_context,
        model_id=recommendation.model_id,
    )


def _recall_agent_memories(
    session: Session,
    incident_id: UUID,
    *,
    embedding_service_factory: EmbeddingServiceFactory,
    searcher: MemoryRecallSearcher,
    memory_limit: int,
) -> MemoryRecallResponse:
    try:
        return recall_similar_memories_for_incident(
            session,
            incident_id,
            top_k=_bounded_memory_limit(memory_limit),
            min_similarity=DEFAULT_MIN_SIMILARITY,
            embedding_service_factory=embedding_service_factory,
            searcher=searcher,
        )
    except IncidentForRecallNotFoundError:
        raise IncidentForAgentNotFoundError("Incident not found") from None
    except MemoryRecallEmbeddingConfigurationUnavailableError:
        raise MemoryAgentEmbeddingConfigurationUnavailableError(
            "Memory recall embeddings are not configured"
        ) from None
    except MemoryRecallEmbeddingUnavailableError:
        raise MemoryAgentEmbeddingUnavailableError(
            "Memory recall embedding generation failed"
        ) from None
    except MemoryRecallResultValidationError:
        raise MemoryAgentRecallUnavailableError(
            "Memory recall results were invalid"
        ) from None


def _bounded_memory_limit(memory_limit: int) -> int:
    return min(max(1, memory_limit), MAX_AGENT_RECALLED_MEMORIES)
