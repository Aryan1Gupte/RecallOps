"""Synchronous memory persistence operations."""

from dataclasses import dataclass
from datetime import datetime
import math
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, Select, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from recallops.models.memory import Memory


class MemoryPersistenceError(RuntimeError):
    """Safe boundary error that does not expose driver details."""


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


def _memory_record_select() -> Select[tuple[object, ...]]:
    return select(
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


def _is_sqlite(session: Session) -> bool:
    bind = session.get_bind()
    return bind.dialect.name == "sqlite"
