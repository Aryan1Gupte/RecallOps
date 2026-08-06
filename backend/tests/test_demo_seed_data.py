from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import sys
from types import ModuleType

from sqlalchemy import select
from sqlalchemy.orm import Session

from recallops.models.incident import Incident
from recallops.models.memory import Memory


def load_seed_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "seed_demo_data.py"
    )
    spec = importlib.util.spec_from_file_location("seed_demo_data", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_demo_definitions_are_well_formed() -> None:
    seed = load_seed_module()
    incident_keys = {incident.key for incident in seed.DEMO_PLAN.incidents}
    memory_keys = {memory.key for memory in seed.DEMO_PLAN.memories}

    assert len(seed.DEMO_PLAN.incidents) == 6
    assert len(seed.DEMO_PLAN.memories) == 8
    assert len(incident_keys) == len(seed.DEMO_PLAN.incidents)
    assert len(memory_keys) == len(seed.DEMO_PLAN.memories)
    assert seed.DEMO_PLAN.rejected_memory_key in memory_keys
    assert seed.DEMO_PLAN.superseded_memory_key in memory_keys
    assert seed.DEMO_PLAN.replacement_memory_key in memory_keys

    valid_memory_types = {"resolution", "failed_action", "procedure", "observation"}
    valid_environments = {"development", "test", "uat", "production"}
    for incident in seed.DEMO_PLAN.incidents:
        assert incident.environment in valid_environments

    for memory in seed.DEMO_PLAN.memories:
        assert memory.incident_key in incident_keys
        assert memory.memory_type in valid_memory_types
        assert memory.summary.strip()


def test_demo_incidents_use_prefix_and_memories_link_to_demo_incidents() -> None:
    seed = load_seed_module()
    incident_keys = {incident.key for incident in seed.DEMO_PLAN.incidents}

    assert all(
        incident.title.startswith(seed.DEMO_PREFIX)
        for incident in seed.DEMO_PLAN.incidents
    )
    assert all(memory.incident_key in incident_keys for memory in seed.DEMO_PLAN.memories)


def test_dry_run_does_not_mutate_or_call_embedding_service(
    db_session: Session,
) -> None:
    seed = load_seed_module()
    output = io.StringIO()

    def fail_if_called():
        raise AssertionError("dry-run must not call Titan")

    summary = seed.seed_demo_data(
        db_session,
        apply=False,
        embedding_service_factory=fail_if_called,
        output=output,
    )

    assert summary.mode == "dry-run"
    assert summary.incidents_would_create == 6
    assert summary.memories_would_create == 8
    assert summary.rejected_would_apply == 1
    assert summary.superseded_would_apply == 1
    assert summary.feedback_would_apply == 4
    assert db_session.scalars(select(Incident)).all() == []
    assert db_session.scalars(select(Memory)).all() == []
    assert "Raw vectors are not printed" in output.getvalue()
