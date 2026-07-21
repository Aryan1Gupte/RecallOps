"""Semantic memory recall service."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from recallops.ai.embedding_protocols import (
    EmbeddingService,
    EmbeddingError,
    EmbeddingResult,
)
from recallops.ai.embedding_text import build_incident_embedding_text
from recallops.ai.protocols import IncidentAnalysisInput, build_incident_analysis_input
from recallops.config import BedrockEmbeddingConfigurationError
from recallops.repositories.incidents import get_incident
from recallops.repositories.memories import (
    SimilarMemoryRecord,
    search_similar_active_memories,
)
from recallops.schemas.memory import (
    MemoryRecallResponse,
    MemoryStatus,
    RecalledMemoryResponse,
)

DEFAULT_RECALL_TOP_K = 5
MAX_RECALL_TOP_K = 10
DEFAULT_MIN_SIMILARITY = 0.60


class IncidentForRecallNotFoundError(RuntimeError):
    """Raised when recall is requested for an incident that does not exist."""


class MemoryRecallEmbeddingUnavailableError(RuntimeError):
    """Raised when an embedding cannot be generated safely for recall."""


class MemoryRecallEmbeddingConfigurationUnavailableError(RuntimeError):
    """Raised when recall embedding settings are incomplete."""


EmbeddingServiceFactory = Callable[[], EmbeddingService]
MemoryRecallSearcher = Callable[
    [Session, tuple[float, ...], int],
    list[SimilarMemoryRecord],
]


def recall_similar_memories_for_incident(
    session: Session,
    incident_id: UUID,
    *,
    top_k: int = DEFAULT_RECALL_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    embedding_service_factory: EmbeddingServiceFactory,
    searcher: MemoryRecallSearcher = search_similar_active_memories,
) -> MemoryRecallResponse:
    """Recall active memories using the selected incident as the query."""

    incident = get_incident(session, incident_id)
    if incident is None:
        raise IncidentForRecallNotFoundError("Incident not found")

    incident_input = build_incident_analysis_input(incident)
    query_context = IncidentAnalysisInput(
        incident_id=incident_input.incident_id,
        title=incident_input.title,
        description=incident_input.description,
        service=incident_input.service,
        environment=incident_input.environment,
        status=incident_input.status,
    )
    # The query context is copied, so the DB transaction can end before the
    # potentially slow Bedrock embedding request.
    session.rollback()

    embedding_text = build_incident_embedding_text(query_context)

    try:
        embedding_service = embedding_service_factory()
        embedding_result = embedding_service.embed(embedding_text)
    except BedrockEmbeddingConfigurationError:
        raise MemoryRecallEmbeddingConfigurationUnavailableError(
            "Memory recall embeddings are not configured"
        ) from None
    except EmbeddingError:
        raise MemoryRecallEmbeddingUnavailableError(
            "Memory recall embedding generation failed"
        ) from None

    _validate_embedding_result(embedding_result)

    bounded_top_k = min(max(1, top_k), MAX_RECALL_TOP_K)
    candidates = searcher(session, embedding_result.vector, bounded_top_k)
    recalled_memories = _apply_semantic_gate(
        candidates,
        min_similarity=min_similarity,
        top_k=bounded_top_k,
    )

    if recalled_memories:
        message = (
            f"Found {len(recalled_memories)} relevant active "
            f"memor{'y' if len(recalled_memories) == 1 else 'ies'}."
        )
    else:
        message = "No relevant active memories were found for this incident."

    return MemoryRecallResponse(
        incident_id=query_context.incident_id,
        query_embedding_model_id=embedding_result.model_id,
        query_embedding_dimension=embedding_result.dimension,
        min_similarity=min_similarity,
        top_k=bounded_top_k,
        memories=recalled_memories,
        message=message,
    )


def _apply_semantic_gate(
    candidates: list[SimilarMemoryRecord],
    *,
    min_similarity: float,
    top_k: int,
) -> list[RecalledMemoryResponse]:
    recalled_memories: list[RecalledMemoryResponse] = []
    for candidate in candidates:
        if candidate.status != MemoryStatus.ACTIVE.value:
            continue
        similarity = 1 - candidate.cosine_distance
        if similarity < min_similarity:
            continue
        recalled_memories.append(
            RecalledMemoryResponse(
                memory_id=candidate.memory_id,
                incident_id=candidate.incident_id,
                memory_type=candidate.memory_type,
                summary=candidate.summary,
                root_cause=candidate.root_cause,
                resolution=candidate.resolution,
                status=candidate.status,
                embedding_model_id=candidate.embedding_model_id,
                embedding_dimension=candidate.embedding_dimension,
                success_count=candidate.success_count,
                failure_count=candidate.failure_count,
                cosine_distance=candidate.cosine_distance,
                similarity=similarity,
            )
        )
        if len(recalled_memories) >= top_k:
            break
    return recalled_memories


def _validate_embedding_result(result: EmbeddingResult) -> None:
    if not isinstance(result, EmbeddingResult):
        raise MemoryRecallEmbeddingUnavailableError(
            "Memory recall embedding was invalid"
        ) from None
