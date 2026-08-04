"""Memory HTTP routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from recallops.ai.dependencies import (
    EmbeddingServiceFactory,
    get_embedding_service_factory,
)
from recallops.database.session import get_db
from recallops.repositories.incidents import IncidentPersistenceError
from recallops.repositories.memories import MemoryPersistenceError
from recallops.schemas.memory import (
    MemoryCreate,
    MemoryFeedbackCreate,
    MemoryFeedbackResponse,
    MemoryResponse,
    MemoryStatus,
    MemoryType,
)
from recallops.services.memories import (
    CreateMemoryCommand,
    LinkedIncidentNotFoundError,
    MemoryEmbeddingConfigurationUnavailableError,
    MemoryEmbeddingUnavailableError,
    MemoryFeedbackConflictError,
    MemoryFeedbackNotFoundError,
    MemoryFeedbackValidationError,
    MemoryValidationError,
    create_memory,
    get_memory,
    list_memories,
    submit_memory_feedback,
)

router = APIRouter(prefix="/memories", tags=["memories"])


def persistence_unavailable() -> HTTPException:
    """Create a generic API error that contains no driver details."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory_endpoint(
    payload: MemoryCreate,
    session: Session = Depends(get_db),
    service_factory: EmbeddingServiceFactory = Depends(
        get_embedding_service_factory
    ),
) -> MemoryResponse:
    command = CreateMemoryCommand(
        incident_id=payload.incident_id,
        memory_type=payload.memory_type.value,
        summary=payload.summary,
        root_cause=payload.root_cause,
        resolution=payload.resolution,
    )
    try:
        memory = create_memory(session, command, service_factory)
    except LinkedIncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        ) from None
    except MemoryValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except MemoryEmbeddingConfigurationUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory embeddings are not configured",
        ) from None
    except MemoryEmbeddingUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory embedding is temporarily unavailable",
        ) from None
    except (IncidentPersistenceError, MemoryPersistenceError):
        raise persistence_unavailable() from None

    return MemoryResponse.model_validate(memory)


@router.get("", response_model=list[MemoryResponse])
def list_memories_endpoint(
    status_filter: MemoryStatus | None = Query(default=None, alias="status"),
    memory_type: MemoryType | None = None,
    incident_id: UUID | None = None,
    session: Session = Depends(get_db),
) -> list[MemoryResponse]:
    try:
        memories = list_memories(
            session,
            status=status_filter.value if status_filter is not None else None,
            memory_type=memory_type.value if memory_type is not None else None,
            incident_id=incident_id,
        )
    except MemoryPersistenceError:
        raise persistence_unavailable() from None

    return [MemoryResponse.model_validate(memory) for memory in memories]


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory_endpoint(
    memory_id: UUID,
    session: Session = Depends(get_db),
) -> MemoryResponse:
    try:
        memory = get_memory(session, memory_id)
    except MemoryPersistenceError:
        raise persistence_unavailable() from None

    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )
    return MemoryResponse.model_validate(memory)


@router.post("/{memory_id}/feedback", response_model=MemoryFeedbackResponse)
def submit_memory_feedback_endpoint(
    memory_id: UUID,
    payload: MemoryFeedbackCreate,
    session: Session = Depends(get_db),
) -> MemoryFeedbackResponse:
    try:
        result = submit_memory_feedback(session, memory_id, payload.outcome.value)
    except MemoryFeedbackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        ) from None
    except MemoryFeedbackConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback is only accepted for active memories",
        ) from None
    except MemoryFeedbackValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None
    except MemoryPersistenceError:
        raise persistence_unavailable() from None

    return MemoryFeedbackResponse.model_validate(result)
