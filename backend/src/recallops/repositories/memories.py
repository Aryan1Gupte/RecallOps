"""Synchronous memory persistence operations."""

from dataclasses import dataclass
from datetime import datetime
import math
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, Select, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from recallops.models.incident import Incident
from recallops.models.memory import Memory


class MemoryPersistenceError(RuntimeError):
    """Safe boundary error that does not expose driver details."""


class MemoryRecordNotFoundError(RuntimeError):
    """Raised when a requested memory row does not exist."""


class MemoryFeedbackNotAcceptedError(RuntimeError):
    """Raised when a memory cannot accept feedback in its current status."""


@dataclass(frozen=True)
class NewMemoryRecord:
    incident_id: UUID | None
    memory_type: str
    summary: str
    root_cause: str | None
    resolution: str | None
    embedding_text: str
    embedding: tuple[float, ...]
    embedding_model_id: str
    embedding_dimension: int


@dataclass(frozen=True)
class MemoryFilters:
    status: str | None = None
    memory_type: str | None = None
    incident_id: UUID | None = None


@dataclass(frozen=True)
class MemoryRecord:
    id: UUID
    incident_id: UUID | None
    memory_type: str
    summary: str
    root_cause: str | None
    resolution: str | None
    embedding_text: str
    embedding_model_id: str
    embedding_dimension: int
    success_count: int
    failure_count: int
    status: str
    superseded_by: UUID | None
    superseded_at: datetime | None
    supersession_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SimilarMemoryRecord:
    memory_id: UUID
    incident_id: UUID | None
    memory_incident_service: str | None
    memory_type: str
    summary: str
    root_cause: str | None
    resolution: str | None
    embedding_model_id: str
    embedding_dimension: int
    success_count: int
    failure_count: int
    status: str
    cosine_distance: float
    created_at: datetime


def create_memory_record(session: Session, payload: NewMemoryRecord) -> MemoryRecord:
    """Persist a memory while keeping the raw vector out of public records."""

    try:
        if _is_sqlite(session):
            record = _create_memory_record_for_sqlite(session, payload)
        else:
            record = _create_memory_record_for_cockroach(session, payload)
        return record
    except SQLAlchemyError:
        session.rollback()
        raise MemoryPersistenceError("Memory persistence failed") from None


def list_memory_records(
    session: Session,
    filters: MemoryFilters | None = None,
) -> list[MemoryRecord]:
    statement = _memory_record_select()
    if filters is not None:
        if filters.status is not None:
            statement = statement.where(Memory.status == filters.status)
        if filters.memory_type is not None:
            statement = statement.where(Memory.memory_type == filters.memory_type)
        if filters.incident_id is not None:
            statement = statement.where(Memory.incident_id == filters.incident_id)

    statement = statement.order_by(Memory.created_at.desc(), Memory.id.desc())

    try:
        rows = session.execute(statement).mappings().all()
    except SQLAlchemyError:
        session.rollback()
        raise MemoryPersistenceError("Memory persistence failed") from None
    return [_memory_record_from_mapping(row) for row in rows]


def get_memory_record(session: Session, memory_id: UUID) -> MemoryRecord | None:
    statement = _memory_record_select().where(Memory.id == memory_id)
    try:
        row = session.execute(statement).mappings().one_or_none()
    except SQLAlchemyError:
        session.rollback()
        raise MemoryPersistenceError("Memory persistence failed") from None
    if row is None:
        return None
    return _memory_record_from_mapping(row)


def record_memory_feedback(
    session: Session,
    memory_id: UUID,
    outcome: str,
) -> MemoryRecord:
    """Atomically increment feedback counters for one active memory."""

    values = {"updated_at": func.now()}
    if outcome == "success":
        values["success_count"] = Memory.success_count + 1
    elif outcome == "failure":
        values["failure_count"] = Memory.failure_count + 1
    else:
        raise ValueError("Memory feedback outcome was invalid")

    statement = (
        update(Memory)
        .where(Memory.id == memory_id, Memory.status == "active")
        .values(**values)
        .returning(*_memory_record_columns())
    )

    try:
        row = session.execute(statement).mappings().one_or_none()
        if row is not None:
            session.commit()
            return _memory_record_from_mapping(row)

        session.rollback()
        status_row = session.execute(
            select(Memory.status).where(Memory.id == memory_id)
        ).scalar_one_or_none()
    except SQLAlchemyError:
        session.rollback()
        raise MemoryPersistenceError("Memory feedback persistence failed") from None

    if status_row is None:
        raise MemoryRecordNotFoundError("Memory not found")
    raise MemoryFeedbackNotAcceptedError("Feedback is only accepted for active memories")


def search_similar_active_memories(
    session: Session,
    query_vector: tuple[float, ...],
    limit: int,
) -> list[SimilarMemoryRecord]:
    """Search active memories by CockroachDB VECTOR cosine distance."""

    try:
        if _is_sqlite(session):
            return _search_similar_active_memories_for_sqlite(
                session,
                query_vector,
                limit,
            )
        return _search_similar_active_memories_for_cockroach(
            session,
            query_vector,
            limit,
        )
    except SQLAlchemyError:
        session.rollback()
        raise MemoryPersistenceError("Memory vector search failed") from None


def _create_memory_record_for_sqlite(
    session: Session,
    payload: NewMemoryRecord,
) -> MemoryRecord:
    memory = Memory(
        incident_id=payload.incident_id,
        memory_type=payload.memory_type,
        summary=payload.summary,
        root_cause=payload.root_cause,
        resolution=payload.resolution,
        embedding_text=payload.embedding_text,
        embedding=_serialize_vector(payload.embedding),
        embedding_model_id=payload.embedding_model_id,
        embedding_dimension=payload.embedding_dimension,
    )
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return _memory_record_from_model(memory)


def _create_memory_record_for_cockroach(
    session: Session,
    payload: NewMemoryRecord,
) -> MemoryRecord:
    memory_id = uuid4()
    statement = text(
        """
        INSERT INTO memories (
            id,
            incident_id,
            memory_type,
            summary,
            root_cause,
            resolution,
            embedding_text,
            embedding,
            embedding_model_id,
            embedding_dimension
        )
        VALUES (
            :id,
            :incident_id,
            :memory_type,
            :summary,
            :root_cause,
            :resolution,
            :embedding_text,
            CAST(:embedding AS VECTOR(1024)),
            :embedding_model_id,
            :embedding_dimension
        )
        RETURNING
            id,
            incident_id,
            memory_type,
            summary,
            root_cause,
            resolution,
            embedding_text,
            embedding_model_id,
            embedding_dimension,
            success_count,
            failure_count,
            status,
            superseded_by,
            superseded_at,
            supersession_reason,
            created_at,
            updated_at
        """
    )
    row = (
        session.execute(
            statement,
            {
                "id": memory_id,
                "incident_id": payload.incident_id,
                "memory_type": payload.memory_type,
                "summary": payload.summary,
                "root_cause": payload.root_cause,
                "resolution": payload.resolution,
                "embedding_text": payload.embedding_text,
                "embedding": _serialize_vector(payload.embedding),
                "embedding_model_id": payload.embedding_model_id,
                "embedding_dimension": payload.embedding_dimension,
            },
        )
        .mappings()
        .one()
    )
    session.commit()
    return _memory_record_from_mapping(row)


def _search_similar_active_memories_for_cockroach(
    session: Session,
    query_vector: tuple[float, ...],
    limit: int,
) -> list[SimilarMemoryRecord]:
    statement = text(
        """
        SELECT
            memories.id AS memory_id,
            memories.incident_id,
            linked_incidents.service AS memory_incident_service,
            memories.memory_type,
            memories.summary,
            memories.root_cause,
            memories.resolution,
            memories.embedding_model_id,
            memories.embedding_dimension,
            memories.success_count,
            memories.failure_count,
            memories.status,
            memories.embedding <=> CAST(:query_vector AS VECTOR(1024)) AS cosine_distance,
            memories.created_at
        FROM memories
        LEFT JOIN incidents AS linked_incidents
            ON memories.incident_id = linked_incidents.id
        WHERE memories.status = 'active'
        ORDER BY memories.embedding <=> CAST(:query_vector AS VECTOR(1024))
        LIMIT :limit
        """
    )
    rows = (
        session.execute(
            statement,
            {
                "query_vector": _serialize_vector(query_vector),
                "limit": max(1, limit),
            },
        )
        .mappings()
        .all()
    )
    return [_similar_memory_record_from_mapping(row) for row in rows]


def _search_similar_active_memories_for_sqlite(
    session: Session,
    query_vector: tuple[float, ...],
    limit: int,
) -> list[SimilarMemoryRecord]:
    statement = (
        select(
            Memory,
            Incident.service.label("memory_incident_service"),
        )
        .outerjoin(Incident, Memory.incident_id == Incident.id)
        .where(Memory.status == "active")
    )
    rows = session.execute(statement).all()
    scored_memories = [
        _similar_memory_record_from_model(
            memory,
            _cosine_distance(memory.embedding, query_vector),
            memory_incident_service,
        )
        for memory, memory_incident_service in rows
    ]
    return sorted(
        scored_memories,
        key=lambda memory: (memory.cosine_distance, str(memory.memory_id)),
    )[: max(1, limit)]


def _memory_record_select() -> Select[tuple[object, ...]]:
    return select(*_memory_record_columns())


def _memory_record_columns() -> tuple[object, ...]:
    return (
        Memory.id.label("id"),
        Memory.incident_id.label("incident_id"),
        Memory.memory_type.label("memory_type"),
        Memory.summary.label("summary"),
        Memory.root_cause.label("root_cause"),
        Memory.resolution.label("resolution"),
        Memory.embedding_text.label("embedding_text"),
        Memory.embedding_model_id.label("embedding_model_id"),
        Memory.embedding_dimension.label("embedding_dimension"),
        Memory.success_count.label("success_count"),
        Memory.failure_count.label("failure_count"),
        Memory.status.label("status"),
        Memory.superseded_by.label("superseded_by"),
        Memory.superseded_at.label("superseded_at"),
        Memory.supersession_reason.label("supersession_reason"),
        Memory.created_at.label("created_at"),
        Memory.updated_at.label("updated_at"),
    )


def _memory_record_from_model(memory: Memory) -> MemoryRecord:
    return MemoryRecord(
        id=memory.id,
        incident_id=memory.incident_id,
        memory_type=memory.memory_type,
        summary=memory.summary,
        root_cause=memory.root_cause,
        resolution=memory.resolution,
        embedding_text=memory.embedding_text,
        embedding_model_id=memory.embedding_model_id,
        embedding_dimension=memory.embedding_dimension,
        success_count=memory.success_count,
        failure_count=memory.failure_count,
        status=memory.status,
        superseded_by=memory.superseded_by,
        superseded_at=memory.superseded_at,
        supersession_reason=memory.supersession_reason,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


def _memory_record_from_mapping(row: RowMapping) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        incident_id=row["incident_id"],
        memory_type=row["memory_type"],
        summary=row["summary"],
        root_cause=row["root_cause"],
        resolution=row["resolution"],
        embedding_text=row["embedding_text"],
        embedding_model_id=row["embedding_model_id"],
        embedding_dimension=row["embedding_dimension"],
        success_count=row["success_count"],
        failure_count=row["failure_count"],
        status=row["status"],
        superseded_by=row["superseded_by"],
        superseded_at=row["superseded_at"],
        supersession_reason=row["supersession_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _similar_memory_record_from_mapping(row: RowMapping) -> SimilarMemoryRecord:
    return SimilarMemoryRecord(
        memory_id=row["memory_id"],
        incident_id=row["incident_id"],
        memory_incident_service=row["memory_incident_service"],
        memory_type=row["memory_type"],
        summary=row["summary"],
        root_cause=row["root_cause"],
        resolution=row["resolution"],
        embedding_model_id=row["embedding_model_id"],
        embedding_dimension=row["embedding_dimension"],
        success_count=row["success_count"],
        failure_count=row["failure_count"],
        status=row["status"],
        cosine_distance=float(row["cosine_distance"]),
        created_at=row["created_at"],
    )


def _similar_memory_record_from_model(
    memory: Memory,
    cosine_distance: float,
    memory_incident_service: str | None,
) -> SimilarMemoryRecord:
    return SimilarMemoryRecord(
        memory_id=memory.id,
        incident_id=memory.incident_id,
        memory_incident_service=memory_incident_service,
        memory_type=memory.memory_type,
        summary=memory.summary,
        root_cause=memory.root_cause,
        resolution=memory.resolution,
        embedding_model_id=memory.embedding_model_id,
        embedding_dimension=memory.embedding_dimension,
        success_count=memory.success_count,
        failure_count=memory.failure_count,
        status=memory.status,
        cosine_distance=cosine_distance,
        created_at=memory.created_at,
    )


def _serialize_vector(vector: tuple[float, ...]) -> str:
    values: list[str] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MemoryPersistenceError("Memory vector was invalid")
        number = float(value)
        if not math.isfinite(number):
            raise MemoryPersistenceError("Memory vector was invalid")
        values.append(repr(number))
    return "[" + ",".join(values) + "]"


def _parse_vector(serialized_vector: str) -> tuple[float, ...]:
    stripped = serialized_vector.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        raise MemoryPersistenceError("Stored memory vector was invalid")
    body = stripped[1:-1].strip()
    if not body:
        raise MemoryPersistenceError("Stored memory vector was invalid")
    try:
        return tuple(float(value) for value in body.split(","))
    except ValueError:
        raise MemoryPersistenceError("Stored memory vector was invalid") from None


def _cosine_distance(
    serialized_memory_vector: str,
    query_vector: tuple[float, ...],
) -> float:
    memory_vector = _parse_vector(serialized_memory_vector)
    if len(memory_vector) != len(query_vector):
        raise MemoryPersistenceError("Stored memory vector dimension was invalid")
    dot = sum(memory_value * query_value for memory_value, query_value in zip(memory_vector, query_vector))
    memory_norm = math.sqrt(sum(value * value for value in memory_vector))
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    if memory_norm == 0 or query_norm == 0:
        raise MemoryPersistenceError("Memory vector norm was invalid")
    return 1 - (dot / (memory_norm * query_norm))


def _is_sqlite(session: Session) -> bool:
    bind = session.get_bind()
    return bind.dialect.name == "sqlite"
