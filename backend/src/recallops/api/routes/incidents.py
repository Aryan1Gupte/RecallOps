"""Incident CRUD HTTP routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from recallops.api.rate_limit import paid_ai_rate_limit
from recallops.ai.bedrock import AnalysisServiceError
from recallops.ai.dependencies import (
    EmbeddingServiceFactory,
    IncidentAnalysisServiceFactory,
    get_embedding_service_factory,
    get_incident_analysis_service_factory,
)
from recallops.ai.embedding_protocols import EmbeddingError
from recallops.ai.embedding_text import (
    build_embedding_text_preview,
    build_incident_embedding_text,
)
from recallops.ai.protocols import build_incident_analysis_input
from recallops.config import (
    BedrockConfigurationError,
    BedrockEmbeddingConfigurationError,
)
from recallops.database.session import get_db
from recallops.repositories.incidents import (
    IncidentPersistenceError,
    create_incident,
    get_incident,
    list_incidents,
)
from recallops.repositories.memories import (
    MemoryPersistenceError,
    search_similar_active_memories,
)
from recallops.schemas.analysis import IncidentAnalysisResponse
from recallops.schemas.embedding import IncidentEmbeddingPreviewResponse
from recallops.schemas.incident import IncidentCreate, IncidentResponse
from recallops.schemas.memory import MemoryRecallResponse
from recallops.services.memory_recall import (
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_RECALL_TOP_K,
    MAX_RECALL_TOP_K,
    MIN_ALLOWED_RECALL_SIMILARITY,
    IncidentForRecallNotFoundError,
    MemoryRecallEmbeddingConfigurationUnavailableError,
    MemoryRecallEmbeddingUnavailableError,
    MemoryRecallResultValidationError,
    MemoryRecallSearcher,
    recall_similar_memories_for_incident,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


def persistence_unavailable() -> HTTPException:
    """Create a generic API error that contains no driver details."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


def get_memory_recall_searcher() -> MemoryRecallSearcher:
    """Return the repository search boundary for dependency overrides."""

    return search_similar_active_memories


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident_endpoint(
    payload: IncidentCreate,
    session: Session = Depends(get_db),
) -> IncidentResponse:
    try:
        return IncidentResponse.model_validate(create_incident(session, payload))
    except IncidentPersistenceError:
        raise persistence_unavailable() from None


@router.get("", response_model=list[IncidentResponse])
def list_incidents_endpoint(
    session: Session = Depends(get_db),
) -> list[IncidentResponse]:
    try:
        return [
            IncidentResponse.model_validate(incident)
            for incident in list_incidents(session)
        ]
    except IncidentPersistenceError:
        raise persistence_unavailable() from None


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident_endpoint(
    incident_id: UUID,
    session: Session = Depends(get_db),
) -> IncidentResponse:
    try:
        incident = get_incident(session, incident_id)
    except IncidentPersistenceError:
        raise persistence_unavailable() from None

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/analysis", response_model=IncidentAnalysisResponse)
def analyze_incident_endpoint(
    incident_id: UUID,
    _: None = Depends(paid_ai_rate_limit),
    session: Session = Depends(get_db),
    service_factory: IncidentAnalysisServiceFactory = Depends(
        get_incident_analysis_service_factory
    ),
) -> IncidentAnalysisResponse:
    """Generate a validated, non-persisted analysis for one incident."""

    try:
        incident = get_incident(session, incident_id)
    except IncidentPersistenceError:
        raise persistence_unavailable() from None

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    analysis_input = build_incident_analysis_input(incident)
    # The incident fields are copied, so the DB transaction can end before the
    # potentially slow Bedrock analysis request.
    session.rollback()

    try:
        service = service_factory()
        return service.analyze(analysis_input)
    except BedrockConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis is not configured",
        ) from None
    except AnalysisServiceError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis is temporarily unavailable",
        ) from None


@router.post(
    "/{incident_id}/embedding-preview",
    response_model=IncidentEmbeddingPreviewResponse,
)
def preview_incident_embedding_endpoint(
    incident_id: UUID,
    _: None = Depends(paid_ai_rate_limit),
    session: Session = Depends(get_db),
    service_factory: EmbeddingServiceFactory = Depends(
        get_embedding_service_factory
    ),
) -> IncidentEmbeddingPreviewResponse:
    """Generate embedding metadata without persisting or returning the vector."""

    try:
        incident = get_incident(session, incident_id)
    except IncidentPersistenceError:
        raise persistence_unavailable() from None

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    incident_input = build_incident_analysis_input(incident)
    # The incident fields are copied, so the DB transaction can end before the
    # potentially slow Titan embedding request.
    session.rollback()
    embedding_text = build_incident_embedding_text(incident_input)

    try:
        result = service_factory().embed(embedding_text)
    except BedrockEmbeddingConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding preview is not configured",
        ) from None
    except EmbeddingError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding preview is temporarily unavailable",
        ) from None

    return IncidentEmbeddingPreviewResponse(
        incident_id=incident_input.incident_id,
        model_id=result.model_id,
        dimension=result.dimension,
        input_text_token_count=result.input_text_token_count,
        text_preview=build_embedding_text_preview(embedding_text),
    )


@router.post("/{incident_id}/memory-recall", response_model=MemoryRecallResponse)
def recall_incident_memories_endpoint(
    incident_id: UUID,
    top_k: int = Query(
        default=DEFAULT_RECALL_TOP_K,
        ge=1,
        le=MAX_RECALL_TOP_K,
    ),
    min_similarity: float = Query(
        default=DEFAULT_MIN_SIMILARITY,
        ge=MIN_ALLOWED_RECALL_SIMILARITY,
        le=1.0,
    ),
    _: None = Depends(paid_ai_rate_limit),
    session: Session = Depends(get_db),
    service_factory: EmbeddingServiceFactory = Depends(
        get_embedding_service_factory
    ),
    searcher: MemoryRecallSearcher = Depends(get_memory_recall_searcher),
) -> MemoryRecallResponse:
    """Recall semantically similar active memories for one incident."""

    try:
        return recall_similar_memories_for_incident(
            session,
            incident_id,
            top_k=top_k,
            min_similarity=min_similarity,
            embedding_service_factory=service_factory,
            searcher=searcher,
        )
    except IncidentForRecallNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from None
    except MemoryRecallEmbeddingConfigurationUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory recall embeddings are not configured",
        ) from None
    except MemoryRecallEmbeddingUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory recall is temporarily unavailable",
        ) from None
    except MemoryRecallResultValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory recall is temporarily unavailable",
        ) from None
    except (IncidentPersistenceError, MemoryPersistenceError):
        raise persistence_unavailable() from None
