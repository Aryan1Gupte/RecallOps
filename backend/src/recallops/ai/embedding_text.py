"""Deterministic incident text used for semantic embeddings."""

from dataclasses import dataclass

EMBEDDING_TEXT_PREVIEW_MAX_CHARS = 1000


@dataclass(frozen=True)
class IncidentEmbeddingInput:
    title: str
    description: str
    service: str
    environment: str
    status: str


def build_incident_embedding_text(incident: IncidentEmbeddingInput) -> str:
    """Build stable semantic text without IDs, timestamps, or analysis output."""

    return "\n".join(
        (
            f"Title: {incident.title.strip()}",
            f"Description: {incident.description.strip()}",
            f"Service: {incident.service.strip()}",
            f"Environment: {incident.environment.strip()}",
            f"Status: {incident.status.strip()}",
        )
    )


def build_embedding_text_preview(text: str) -> str:
    """Limit API preview size without changing the text sent for embedding."""

    if len(text) <= EMBEDDING_TEXT_PREVIEW_MAX_CHARS:
        return text
    return text[: EMBEDDING_TEXT_PREVIEW_MAX_CHARS - 1].rstrip() + "…"
