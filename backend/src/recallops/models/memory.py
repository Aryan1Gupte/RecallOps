"""SQLAlchemy memory model.

The Alembic migration owns the CockroachDB-specific VECTOR column type. This
model keeps the test metadata portable so SQLite does not need to understand
CockroachDB vector DDL.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from recallops.database.base import Base


class Memory(Base):
    """A persisted long-term memory with private embedding storage."""

    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "memory_type IN ('resolution', 'failed_action', 'procedure', 'observation')",
            name="ck_memories_memory_type",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'rejected')",
            name="ck_memories_status",
        ),
        CheckConstraint(
            "embedding_dimension = 1024",
            name="ck_memories_embedding_dimension",
        ),
        CheckConstraint(
            "success_count >= 0 AND failure_count >= 0",
            name="ck_memories_counts_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    incident_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1024,
        server_default=text("1024"),
    )
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memories.id"),
        nullable=True,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    supersession_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
