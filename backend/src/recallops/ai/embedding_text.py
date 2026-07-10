"""Deterministic incident text used for semantic embeddings."""

from recallops.ai.protocols import IncidentAnalysisInput

EMBEDDING_TEXT_PREVIEW_MAX_CHARS = 1000


def build_incident_embedding_text(incident: IncidentAnalysisInput) -> str:
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
