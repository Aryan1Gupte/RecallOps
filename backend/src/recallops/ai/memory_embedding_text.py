"""Deterministic memory text used for persisted semantic embeddings."""

from typing import Protocol


class MemoryIncidentContext(Protocol):
    title: str
    service: str
    environment: str


def _optional_text(value: str | None) -> str:
    if value is None:
        return "Not provided"
    stripped = value.strip()
    return stripped or "Not provided"


def build_memory_embedding_text(
    *,
    memory_type: str,
    summary: str,
    root_cause: str | None,
    resolution: str | None,
    incident: MemoryIncidentContext | None = None,
) -> str:
    """Build stable semantic text without IDs, timestamps, or raw AI output."""

    lines = [
        f"Memory Type: {memory_type.strip()}",
        f"Summary: {summary.strip()}",
        f"Root Cause: {_optional_text(root_cause)}",
        f"Resolution: {_optional_text(resolution)}",
    ]

    if incident is not None:
        lines.extend(
            [
                f"Incident Title: {incident.title.strip()}",
                f"Incident Service: {incident.service.strip()}",
                f"Incident Environment: {incident.environment.strip()}",
            ]
        )

    return "\n".join(lines).strip()
