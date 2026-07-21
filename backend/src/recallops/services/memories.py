"""Memory application service."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from recallops.ai.embedding_protocols import (
    EmbeddingService,
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


@dataclass(frozen=True)
class CreateMemoryCommand:
    """Service-layer command for creating memories from any caller."""

    incident_id: UUID | None
    memory_type: str
    summary: str
    root_cause: str | None = None
    resolution: str | None = None


@dataclass(frozen=True)
class LinkedIncidentContext:
    """Safe incident fields copied before blocking embedding calls."""

    title: str
    service: str
    environment: str


class LinkedIncidentNotFoundError(RuntimeError):
    """Raised when a client links a memory to an incident that does not exist."""


class MemoryValidationError(RuntimeError):
    """Raised when memory content is valid JSON but not useful to persist."""


class MemoryEmbeddingUnavailableError(RuntimeError):
    """Raised when an embedding cannot be safely generated for a memory."""


class MemoryEmbeddingConfigurationUnavailableError(RuntimeError):
    """Raised when memory embedding settings are incomplete."""


EmbeddingServiceFactory = Callable[[], EmbeddingService]


def create_memory(
    session: Session,
    command: CreateMemoryCommand,
    embedding_service_factory: EmbeddingServiceFactory,
) -> MemoryRecord:
    """Create a memory after verifying context and generating its embedding."""

    incident_context = None
    if command.incident_id is not None:
        incident = get_incident(session, command.incident_id)
        if incident is None:
            raise LinkedIncidentNotFoundError("Linked incident not found")
        if _normalized_text(command.summary) == _normalized_text(incident.title):
            raise MemoryValidationError(
                "Memory summary must describe what to remember, not repeat the incident title"
            )
        incident_context = LinkedIncidentContext(
            title=incident.title,
            service=incident.service,
            environment=incident.environment,
        )
        # The linked incident fields are copied, so the DB transaction can end
        # before the potentially slow Bedrock embedding request.
        session.rollback()

    embedding_text = build_memory_embedding_text(
        memory_type=command.memory_type,
        summary=command.summary,
        root_cause=command.root_cause,
        resolution=command.resolution,
        incident=incident_context,
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
            incident_id=command.incident_id,
            memory_type=command.memory_type,
            summary=command.summary,
            root_cause=command.root_cause,
            resolution=command.resolution,
            embedding_text=embedding_text,
            embedding=embedding_result.vector,
            embedding_model_id=embedding_result.model_id,
            embedding_dimension=embedding_result.dimension,
        ),
    )


def list_memories(
    session: Session,
    *,
    status: str | None = None,
    memory_type: str | None = None,
    incident_id: UUID | None = None,
) -> list[MemoryRecord]:
    return list_memory_records(
        session,
        MemoryFilters(
            status=status,
            memory_type=memory_type,
            incident_id=incident_id,
        ),
    )


def get_memory(session: Session, memory_id: UUID) -> MemoryRecord | None:
    return get_memory_record(session, memory_id)


def _validate_embedding_result(result: EmbeddingResult) -> None:
    if not isinstance(result, EmbeddingResult):
        raise MemoryEmbeddingUnavailableError("Memory embedding was invalid") from None


def _normalized_text(value: str) -> str:
    return value.strip().casefold()
