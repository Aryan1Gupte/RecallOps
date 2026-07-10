"""Memory application service."""

from collections.abc import Callable
import math
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from recallops.ai.embedding_protocols import (
    EMBEDDING_DIMENSIONS,
    EmbeddingError,
    EmbeddingResult,
)
from recallops.ai.memory_embedding_text import build_memory_embedding_text
from recallops.config import BedrockEmbeddingConfigurationError
from recallops.repositories.incidents import get_incident
from recallops.repositories.memories import (
    MemoryFilters,
    MemoryRecord,
    NewMemoryRecord,
    create_memory_record,
    get_memory_record,
    list_memory_records,
)
from recallops.schemas.memory import MemoryCreate, MemoryStatus, MemoryType


class LinkedIncidentNotFoundError(RuntimeError):
    """Raised when a client links a memory to an incident that does not exist."""


class MemoryEmbeddingUnavailableError(RuntimeError):
    """Raised when an embedding cannot be safely generated for a memory."""


class MemoryEmbeddingConfigurationUnavailableError(RuntimeError):
    """Raised when memory embedding settings are incomplete."""


class EmbeddingService(Protocol):
    def embed(self, text: str) -> EmbeddingResult: ...


EmbeddingServiceFactory = Callable[[], EmbeddingService]


def create_memory(
    session: Session,
    payload: MemoryCreate,
    embedding_service_factory: EmbeddingServiceFactory,
) -> MemoryRecord:
    """Create a memory after verifying context and generating its embedding."""

    incident = None
    if payload.incident_id is not None:
        incident = get_incident(session, payload.incident_id)
        if incident is None:
            raise LinkedIncidentNotFoundError("Linked incident not found")

    embedding_text = build_memory_embedding_text(
        memory_type=payload.memory_type.value,
        summary=payload.summary,
        root_cause=payload.root_cause,
        resolution=payload.resolution,
        incident=incident,
    )

    try:
        embedding_service = embedding_service_factory()
        embedding_result = embedding_service.embed(embedding_text)
    except BedrockEmbeddingConfigurationError:
        raise MemoryEmbeddingConfigurationUnavailableError(
            "Memory embeddings are not configured"
        ) from None
    except EmbeddingError:
        raise MemoryEmbeddingUnavailableError(
            "Memory embedding generation failed"
        ) from None

    _validate_embedding_result(embedding_result)

    return create_memory_record(
        session,
        NewMemoryRecord(
            incident_id=payload.incident_id,
            memory_type=payload.memory_type.value,
            summary=payload.summary,
            root_cause=payload.root_cause,
            resolution=payload.resolution,
            embedding_text=embedding_text,
            embedding=embedding_result.vector,
            embedding_model_id=embedding_result.model_id,
            embedding_dimension=embedding_result.dimension,
        ),
    )


def list_memories(
    session: Session,
    *,
    status: MemoryStatus | None = None,
    memory_type: MemoryType | None = None,
    incident_id: UUID | None = None,
) -> list[MemoryRecord]:
    return list_memory_records(
        session,
        MemoryFilters(
            status=status.value if status is not None else None,
            memory_type=memory_type.value if memory_type is not None else None,
            incident_id=incident_id,
        ),
    )


def get_memory(session: Session, memory_id: UUID) -> MemoryRecord | None:
    return get_memory_record(session, memory_id)


def _validate_embedding_result(result: EmbeddingResult) -> None:
    if result.dimension != EMBEDDING_DIMENSIONS:
        raise MemoryEmbeddingUnavailableError(
            "Memory embedding dimension was invalid"
        )
    if len(result.vector) != EMBEDDING_DIMENSIONS:
        raise MemoryEmbeddingUnavailableError(
            "Memory embedding vector length was invalid"
        )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in result.vector
    ):
        raise MemoryEmbeddingUnavailableError("Memory embedding vector was invalid")
