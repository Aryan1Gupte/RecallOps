#!/usr/bin/env python3
"""Seed repeatable RecallOps demo incidents and memories.

The script is dry-run by default. Use --apply to create or update demo records.
It never prints database URLs, credentials, raw vectors, or provider payloads.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import TextIO
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from recallops.ai.dependencies import get_embedding_service_factory
from recallops.ai.embedding_protocols import EmbeddingService
from recallops.config import (
    BedrockEmbeddingConfigurationError,
    DatabaseConfigurationError,
)
from recallops.database.session import get_session_factory
from recallops.models.incident import Incident
from recallops.models.memory import Memory
from recallops.repositories.incidents import (
    IncidentPersistenceError,
    create_incident,
    list_incidents,
)
from recallops.repositories.memories import MemoryPersistenceError, list_memory_records
from recallops.schemas.incident import IncidentCreate
from recallops.services.memories import (
    CreateMemoryCommand,
    MemoryEmbeddingConfigurationUnavailableError,
    MemoryEmbeddingUnavailableError,
    MemoryLifecycleConflictError,
    MemoryLifecycleNotFoundError,
    create_memory,
    reject_memory,
    supersede_memory,
)

DEMO_PREFIX = "Demo — "
LEGACY_DEMO_PREFIX = "Demo —"
REJECTED_VAGUE_REASON = "Rejected because the memory is too vague for reliable recall."
SUPERSESSION_REASON = "Newer runbook includes cache clearing and warmup steps."


@dataclass(frozen=True)
class DemoIncidentDefinition:
    key: str
    title: str
    description: str
    service: str
    environment: str


@dataclass(frozen=True)
class DemoMemoryDefinition:
    key: str
    incident_key: str
    memory_type: str
    summary: str
    root_cause: str | None
    resolution: str | None


@dataclass(frozen=True)
class DemoFeedbackDefinition:
    memory_key: str
    success_count: int
    failure_count: int


@dataclass(frozen=True)
class DemoPlan:
    incidents: tuple[DemoIncidentDefinition, ...]
    memories: tuple[DemoMemoryDefinition, ...]
    rejected_memory_key: str
    superseded_memory_key: str
    replacement_memory_key: str
    feedback_counts: tuple[DemoFeedbackDefinition, ...]


@dataclass
class SeedSummary:
    mode: str
    incidents_created: int = 0
    incidents_skipped: int = 0
    incidents_would_create: int = 0
    incidents_renamed: int = 0
    incidents_would_rename: int = 0
    memories_created: int = 0
    memories_skipped: int = 0
    memories_would_create: int = 0
    rejected_applied: int = 0
    rejected_already: int = 0
    rejected_would_apply: int = 0
    superseded_applied: int = 0
    superseded_already: int = 0
    superseded_would_apply: int = 0
    feedback_applied: int = 0
    feedback_already: int = 0
    feedback_would_apply: int = 0


EmbeddingServiceFactory = Callable[[], EmbeddingService]


DEMO_PLAN = DemoPlan(
    incidents=(
        DemoIncidentDefinition(
            key="checkout_cache_latency",
            title=f"{DEMO_PREFIX}Checkout cache latency",
            description=(
                "Checkout API latency increased after workers served stale cache "
                "entries during peak traffic."
            ),
            service="checkout-api",
            environment="production",
        ),
        DemoIncidentDefinition(
            key="checkout_cache_latency_recurrence",
            title=f"{DEMO_PREFIX}Checkout cache latency recurrence",
            description=(
                "Checkout latency returned after cache drift caused stale "
                "worker-local state."
            ),
            service="checkout-api",
            environment="production",
        ),
        DemoIncidentDefinition(
            key="nightly_batch_duplicate_transaction_ids",
            title=f"{DEMO_PREFIX}Nightly batch duplicate transaction IDs",
            description=(
                "Nightly transaction batch failed because duplicate transaction "
                "identifiers appeared in the source file."
            ),
            service="transaction-batch",
            environment="production",
        ),
        DemoIncidentDefinition(
            key="payment_retry_storm",
            title=f"{DEMO_PREFIX}Payment retry storm",
            description=(
                "Payment processor generated repeated retries after a downstream "
                "timeout, increasing queue depth."
            ),
            service="payment-worker",
            environment="production",
        ),
        DemoIncidentDefinition(
            key="failed_restart_action",
            title=f"{DEMO_PREFIX}Failed restart action",
            description=(
                "Restarting the payment worker did not reduce the retry storm "
                "because the downstream provider was still timing out."
            ),
            service="payment-worker",
            environment="production",
        ),
        DemoIncidentDefinition(
            key="policy_document_upload_timeout",
            title=f"{DEMO_PREFIX}Policy document upload timeout",
            description=(
                "Policy document upload requests timed out after the document "
                "service connection pool was exhausted."
            ),
            service="document-service",
            environment="uat",
        ),
    ),
    memories=(
        DemoMemoryDefinition(
            key="active_checkout_resolution",
            incident_key="checkout_cache_latency",
            memory_type="resolution",
            summary=(
                "Checkout cache latency is resolved by restarting checkout workers "
                "and clearing stale cache state."
            ),
            root_cause=(
                "Worker-local cache entries drifted from the shared cache during "
                "peak traffic."
            ),
            resolution=(
                "Restart checkout workers, clear stale cache state, and monitor "
                "latency before returning traffic."
            ),
        ),
        DemoMemoryDefinition(
            key="older_checkout_procedure",
            incident_key="checkout_cache_latency",
            memory_type="procedure",
            summary="Restart checkout workers when cache latency appears.",
            root_cause="Checkout workers may hold stale cache entries.",
            resolution="Restart checkout workers.",
        ),
        DemoMemoryDefinition(
            key="replacement_checkout_procedure",
            incident_key="checkout_cache_latency",
            memory_type="procedure",
            summary=(
                "Restart checkout workers and clear stale cache before retrying "
                "checkout traffic."
            ),
            root_cause="Restart alone may leave stale cache state behind.",
            resolution=(
                "Restart workers, clear stale cache, warm critical keys, and then "
                "retry checkout traffic."
            ),
        ),
        DemoMemoryDefinition(
            key="rejected_vague_checkout_memory",
            incident_key="checkout_cache_latency",
            memory_type="observation",
            summary="Checkout was slow and something needed fixing.",
            root_cause=None,
            resolution=None,
        ),
        DemoMemoryDefinition(
            key="active_duplicate_transaction_resolution",
            incident_key="nightly_batch_duplicate_transaction_ids",
            memory_type="resolution",
            summary=(
                "Nightly batch failures from duplicate transaction IDs are fixed "
                "by deduplicating the source file before replay."
            ),
            root_cause="Source file contained repeated transaction identifiers.",
            resolution=(
                "Deduplicate the source file, validate unique transaction IDs, "
                "and replay the batch."
            ),
        ),
        DemoMemoryDefinition(
            key="failed_restart_action_memory",
            incident_key="failed_restart_action",
            memory_type="failed_action",
            summary=(
                "Restarting the payment worker alone does not fix retry storms "
                "caused by downstream provider timeouts."
            ),
            root_cause=(
                "The downstream payment provider was still timing out, so local "
                "restarts did not remove queued retries."
            ),
            resolution=(
                "Pause retries, confirm provider recovery, drain the queue "
                "gradually, then resume workers."
            ),
        ),
        DemoMemoryDefinition(
            key="active_payment_retry_procedure",
            incident_key="payment_retry_storm",
            memory_type="procedure",
            summary=(
                "Payment retry storms should be controlled by pausing retries and "
                "draining queues gradually."
            ),
            root_cause="Downstream timeout caused repeated retry accumulation.",
            resolution=(
                "Pause retry consumers, confirm provider health, reduce "
                "concurrency, and drain queue in batches."
            ),
        ),
        DemoMemoryDefinition(
            key="active_document_service_observation",
            incident_key="policy_document_upload_timeout",
            memory_type="observation",
            summary=(
                "Document upload timeouts can indicate connection pool exhaustion "
                "in the document service."
            ),
            root_cause=(
                "Connection pool saturation prevented upload requests from "
                "completing."
            ),
            resolution=(
                "Check pool usage, increase pool capacity if safe, and recycle "
                "stuck connections."
            ),
        ),
    ),
    rejected_memory_key="rejected_vague_checkout_memory",
    superseded_memory_key="older_checkout_procedure",
    replacement_memory_key="replacement_checkout_procedure",
    feedback_counts=(
        DemoFeedbackDefinition("active_checkout_resolution", 2, 0),
        DemoFeedbackDefinition("active_duplicate_transaction_resolution", 1, 0),
        DemoFeedbackDefinition("failed_restart_action_memory", 1, 1),
        DemoFeedbackDefinition("active_document_service_observation", 0, 1),
    ),
)


def seed_demo_data(
    session: Session,
    *,
    apply: bool,
    embedding_service_factory: EmbeddingServiceFactory | None = None,
    output: TextIO = sys.stdout,
) -> SeedSummary:
    """Create or preview the repeatable demo dataset."""

    summary = SeedSummary(mode="apply" if apply else "dry-run")
    incident_records = _plan_incidents(session, apply=apply, summary=summary)
    memory_records = _plan_memories(
        session,
        incident_records,
        apply=apply,
        summary=summary,
        embedding_service_factory=embedding_service_factory,
    )
    _plan_rejection(session, memory_records, apply=apply, summary=summary)
    _plan_supersession(session, memory_records, apply=apply, summary=summary)
    _plan_feedback_counts(session, memory_records, apply=apply, summary=summary)
    print_summary(summary, output=output)
    return summary


def print_summary(summary: SeedSummary, *, output: TextIO = sys.stdout) -> None:
    action = "created" if summary.mode == "apply" else "would create"
    mutation = "applied" if summary.mode == "apply" else "would apply"
    print(f"Mode: {summary.mode}", file=output)
    print(
        "Incidents: "
        f"{action} {summary.incidents_created if summary.mode == 'apply' else summary.incidents_would_create}, "
        f"skipped {summary.incidents_skipped}, "
        f"{'renamed' if summary.mode == 'apply' else 'would rename'} "
        f"{summary.incidents_renamed if summary.mode == 'apply' else summary.incidents_would_rename}",
        file=output,
    )
    print(
        "Memories: "
        f"{action} {summary.memories_created if summary.mode == 'apply' else summary.memories_would_create}, "
        f"skipped {summary.memories_skipped}",
        file=output,
    )
    print(
        "Rejected memory: "
        f"{mutation} {summary.rejected_applied if summary.mode == 'apply' else summary.rejected_would_apply}, "
        f"already rejected {summary.rejected_already}",
        file=output,
    )
    print(
        "Supersession: "
        f"{mutation} {summary.superseded_applied if summary.mode == 'apply' else summary.superseded_would_apply}, "
        f"already superseded {summary.superseded_already}",
        file=output,
    )
    print(
        "Feedback counts: "
        f"{mutation} {summary.feedback_applied if summary.mode == 'apply' else summary.feedback_would_apply}, "
        f"already matched {summary.feedback_already}",
        file=output,
    )
    print("Raw vectors are not printed by this script.", file=output)


def _plan_incidents(
    session: Session,
    *,
    apply: bool,
    summary: SeedSummary,
) -> dict[str, Incident | None]:
    existing_by_title = {incident.title: incident for incident in list_incidents(session)}
    records: dict[str, Incident | None] = {}

    for definition in DEMO_PLAN.incidents:
        existing = existing_by_title.get(definition.title)
        if existing is not None:
            summary.incidents_skipped += 1
            records[definition.key] = existing
            continue

        legacy = existing_by_title.get(_legacy_incident_title(definition))
        if legacy is not None:
            if apply:
                _rename_demo_incident(
                    session,
                    legacy,
                    new_title=definition.title,
                )
                summary.incidents_renamed += 1
            else:
                summary.incidents_would_rename += 1
            records[definition.key] = legacy
            continue

        if not apply:
            summary.incidents_would_create += 1
            records[definition.key] = None
            continue

        incident = create_incident(
            session,
            IncidentCreate(
                title=definition.title,
                description=definition.description,
                service=definition.service,
                environment=definition.environment,
            ),
        )
        summary.incidents_created += 1
        records[definition.key] = incident

    return records


def _legacy_incident_title(definition: DemoIncidentDefinition) -> str:
    return LEGACY_DEMO_PREFIX + definition.title.removeprefix(DEMO_PREFIX)


def _rename_demo_incident(
    session: Session,
    incident: Incident,
    *,
    new_title: str,
) -> None:
    statement = (
        update(Incident)
        .where(
            Incident.id == incident.id,
            Incident.title == incident.title,
            Incident.title.startswith(LEGACY_DEMO_PREFIX),
        )
        .values(title=new_title, updated_at=func.now())
        .returning(Incident.id)
    )
    try:
        renamed_id = session.execute(statement).scalar_one_or_none()
        if renamed_id is None:
            session.rollback()
            raise DemoSeedError("Demo incident rename target was not found")
        session.commit()
        session.refresh(incident)
    except SQLAlchemyError:
        session.rollback()
        raise DemoSeedError("Demo incident rename failed") from None


def _plan_memories(
    session: Session,
    incident_records: dict[str, Incident | None],
    *,
    apply: bool,
    summary: SeedSummary,
    embedding_service_factory: EmbeddingServiceFactory | None,
) -> dict[str, Memory | None]:
    existing_by_summary = {
        memory.summary: memory for memory in list_memory_records(session)
    }
    records: dict[str, Memory | None] = {}
    service_factory = embedding_service_factory or get_embedding_service_factory()

    for definition in DEMO_PLAN.memories:
        existing = existing_by_summary.get(definition.summary)
        if existing is not None:
            summary.memories_skipped += 1
            records[definition.key] = _load_memory_model(session, existing.id)
            continue

        if not apply:
            summary.memories_would_create += 1
            records[definition.key] = None
            continue

        incident = incident_records[definition.incident_key]
        if incident is None:
            raise DemoSeedError("Demo incident was unavailable for memory creation")
        created = create_memory(
            session,
            CreateMemoryCommand(
                incident_id=incident.id,
                memory_type=definition.memory_type,
                summary=definition.summary,
                root_cause=definition.root_cause,
                resolution=definition.resolution,
            ),
            service_factory,
        )
        summary.memories_created += 1
        records[definition.key] = _load_memory_model(session, created.id)

    return records


def _plan_rejection(
    session: Session,
    memory_records: dict[str, Memory | None],
    *,
    apply: bool,
    summary: SeedSummary,
) -> None:
    memory = memory_records[DEMO_PLAN.rejected_memory_key]
    if memory is None:
        summary.rejected_would_apply += 1
        return
    if memory.status == "rejected":
        summary.rejected_already += 1
        return
    if not apply:
        summary.rejected_would_apply += 1
        return

    reject_memory(session, memory.id, REJECTED_VAGUE_REASON)
    summary.rejected_applied += 1
    _refresh(session, memory)


def _plan_supersession(
    session: Session,
    memory_records: dict[str, Memory | None],
    *,
    apply: bool,
    summary: SeedSummary,
) -> None:
    original = memory_records[DEMO_PLAN.superseded_memory_key]
    replacement = memory_records[DEMO_PLAN.replacement_memory_key]
    if original is None or replacement is None:
        summary.superseded_would_apply += 1
        return
    if original.status == "superseded":
        summary.superseded_already += 1
        return
    if not apply:
        summary.superseded_would_apply += 1
        return

    supersede_memory(session, original.id, replacement.id, SUPERSESSION_REASON)
    summary.superseded_applied += 1
    _refresh(session, original)


def _plan_feedback_counts(
    session: Session,
    memory_records: dict[str, Memory | None],
    *,
    apply: bool,
    summary: SeedSummary,
) -> None:
    definitions_by_key = {memory.key: memory for memory in DEMO_PLAN.memories}
    for feedback in DEMO_PLAN.feedback_counts:
        memory = memory_records[feedback.memory_key]
        if memory is None:
            summary.feedback_would_apply += 1
            continue
        if (
            memory.success_count == feedback.success_count
            and memory.failure_count == feedback.failure_count
        ):
            summary.feedback_already += 1
            continue
        if not apply:
            summary.feedback_would_apply += 1
            continue

        _set_demo_feedback_counts(
            session,
            memory_id=memory.id,
            expected_summary=definitions_by_key[feedback.memory_key].summary,
            success_count=feedback.success_count,
            failure_count=feedback.failure_count,
        )
        summary.feedback_applied += 1
        _refresh(session, memory)


def _set_demo_feedback_counts(
    session: Session,
    *,
    memory_id: UUID,
    expected_summary: str,
    success_count: int,
    failure_count: int,
) -> None:
    """Set exact demo counters without touching non-demo or mismatched rows."""

    statement = (
        update(Memory)
        .where(Memory.id == memory_id, Memory.summary == expected_summary)
        .values(
            success_count=success_count,
            failure_count=failure_count,
            updated_at=func.now(),
        )
        .returning(Memory.id)
    )
    try:
        updated_id = session.execute(statement).scalar_one_or_none()
        if updated_id is None:
            session.rollback()
            raise DemoSeedError("Demo memory counter update target was not found")
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise DemoSeedError("Demo feedback count update failed") from None


def _load_memory_model(session: Session, memory_id: UUID) -> Memory:
    memory = session.get(Memory, memory_id)
    if memory is None:
        raise DemoSeedError("Demo memory was not found after creation")
    return memory


def _refresh(session: Session, memory: Memory) -> None:
    session.refresh(memory)


class DemoSeedError(RuntimeError):
    """Safe script error that avoids credentials, provider payloads, and vectors."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed repeatable RecallOps demo data."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview demo changes without mutating the database or calling Titan.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Create/update demo records using the configured database and Titan.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    apply_changes = bool(args.apply)

    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            seed_demo_data(
                session,
                apply=apply_changes,
                embedding_service_factory=get_embedding_service_factory(),
            )
    except (
        DatabaseConfigurationError,
        IncidentPersistenceError,
        MemoryPersistenceError,
        MemoryEmbeddingConfigurationUnavailableError,
        MemoryEmbeddingUnavailableError,
        BedrockEmbeddingConfigurationError,
        ValidationError,
        MemoryLifecycleConflictError,
        MemoryLifecycleNotFoundError,
        DemoSeedError,
    ) as exc:
        print(f"Demo seed failed safely: {exc}", file=sys.stderr)
        return 1

    if not apply_changes:
        print("Dry-run only. Re-run with --apply to create or update demo records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
