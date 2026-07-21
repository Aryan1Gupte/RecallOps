"""Provider-neutral embedding boundary and validated internal result."""

from dataclasses import dataclass
import math
from typing import Protocol

EMBEDDING_DIMENSIONS = 1024
"""Vector width every embedding provider must produce.

Lives here, not in a provider module, so future consumers (e.g. the
CockroachDB VECTOR column) can depend on the provider-neutral boundary
instead of a Titan-specific implementation detail.
"""


class EmbeddingError(RuntimeError):
    """Base safe error for embedding input, provider, or response failures."""


class EmbeddingInputError(EmbeddingError):
    """Raised when embedding input is empty."""


class EmbeddingValidationError(EmbeddingError):
    """Raised when provider output violates the internal embedding contract."""


class EmbeddingServiceError(EmbeddingError):
    """Raised without provider details when an embedding request fails."""


class EmbeddingService(Protocol):
    """Contract implemented by any embedding provider."""

    def embed(self, text: str) -> "EmbeddingResult":
        """Generate and validate an embedding for backend-internal use."""

        ...


@dataclass(frozen=True)
class EmbeddingResult:
    """Internal embedding result; vectors never cross the public API boundary."""

    vector: tuple[float, ...]
    dimension: int
    input_text_token_count: int
    model_id: str

    def __post_init__(self) -> None:
        if not self.vector:
            raise EmbeddingValidationError("Embedding vector must not be empty")
        if self.dimension != EMBEDDING_DIMENSIONS:
            raise EmbeddingValidationError(
                "Embedding dimension must equal configured vector width"
            )
        if self.dimension != len(self.vector):
            raise EmbeddingValidationError(
                "Embedding dimension must equal vector length"
            )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in self.vector
        ):
            raise EmbeddingValidationError(
                "Embedding vector must contain only finite numeric values"
            )
        if self.input_text_token_count < 0:
            raise EmbeddingValidationError(
                "Embedding input token count must not be negative"
            )
        if not self.model_id.strip():
            raise EmbeddingValidationError("Embedding model ID must not be blank")
