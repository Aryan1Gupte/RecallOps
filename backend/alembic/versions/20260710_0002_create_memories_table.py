"""Create the memories table with CockroachDB vector storage.

Revision ID: 20260710_0002
Revises: 20260704_0001
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260710_0002"
down_revision: str | None = "20260704_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE memories (
            id UUID PRIMARY KEY,
            incident_id UUID NULL REFERENCES incidents(id) ON DELETE SET NULL,
            memory_type STRING(50) NOT NULL,
            summary TEXT NOT NULL,
            root_cause TEXT NULL,
            resolution TEXT NULL,
            embedding_text TEXT NOT NULL,
            embedding VECTOR(1024) NOT NULL,
            embedding_model_id STRING(200) NOT NULL,
            embedding_dimension INT4 NOT NULL DEFAULT 1024,
            success_count INT4 NOT NULL DEFAULT 0,
            failure_count INT4 NOT NULL DEFAULT 0,
            status STRING(30) NOT NULL DEFAULT 'active',
            superseded_by UUID NULL REFERENCES memories(id),
            superseded_at TIMESTAMPTZ NULL,
            supersession_reason TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_memories_memory_type
                CHECK (memory_type IN (
                    'resolution',
                    'failed_action',
                    'procedure',
                    'observation'
                )),
            CONSTRAINT ck_memories_status
                CHECK (status IN ('active', 'superseded', 'rejected')),
            CONSTRAINT ck_memories_embedding_dimension
                CHECK (embedding_dimension = 1024),
            CONSTRAINT ck_memories_counts_nonnegative
                CHECK (success_count >= 0 AND failure_count >= 0),
            VECTOR INDEX memories_embedding_vector_idx
                (embedding vector_cosine_ops)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("memories")
