import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from recallops.database.url import normalize_database_url
from recallops.repositories.memories import NewMemoryRecord, create_memory_record

pytestmark = pytest.mark.skipif(
    os.getenv("RECALLOPS_RUN_COCKROACH_INTEGRATION") != "1",
    reason="CockroachDB integration test is skipped by default",
)


def test_cockroach_memory_insert_path_excludes_raw_vector() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for CockroachDB integration")

    engine = create_engine(
        normalize_database_url(database_url),
        hide_parameters=True,
        pool_pre_ping=True,
    )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    vector = tuple(1e-6 if index % 2 == 0 else -2e-6 for index in range(1024))

    with Session() as session:
        memory = create_memory_record(
            session,
            NewMemoryRecord(
                incident_id=None,
                memory_type="observation",
                summary="Integration test memory insert path",
                root_cause=None,
                resolution=None,
                embedding_text=(
                    "Memory Type: observation\n"
                    "Summary: Integration test memory insert path"
                ),
                embedding=vector,
                embedding_model_id="fake-integration-model",
                embedding_dimension=1024,
            ),
        )

        assert memory.embedding_dimension == 1024
        assert memory.embedding_model_id == "fake-integration-model"
        assert "embedding" not in memory.__dict__

        session.execute(
            text("DELETE FROM memories WHERE id = :memory_id"),
            {"memory_id": memory.id},
        )
        session.commit()

    engine.dispose()
