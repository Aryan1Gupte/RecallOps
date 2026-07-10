"""Public metadata-only embedding preview schema."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class IncidentEmbeddingPreviewResponse(BaseModel):
    """Embedding metadata safe to return without the underlying vector."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    model_id: NonBlankText
    dimension: int = Field(gt=0)
    input_text_token_count: int = Field(ge=0)
    text_preview: NonBlankText
