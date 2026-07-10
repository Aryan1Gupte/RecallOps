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
    MemoryResponse,
    MemoryStatus,
    MemoryType,
)
from recallops.services.memories import (
    LinkedIncidentNotFoundError,
    MemoryEmbeddingConfigurationUnavailableError,
    MemoryEmbeddingUnavailableError,
    create_memory,
    get_memory,
    list_memories,
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
    try:
        memory = create_memory(session, payload, service_factory)
    except LinkedIncidentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
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
            status=status_filter,
            memory_type=memory_type,
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
