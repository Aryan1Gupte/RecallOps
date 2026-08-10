"""Provider-neutral incident analysis boundary."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from recallops.schemas.agent import ModelMemoryAssistedRecommendationPayload
from recallops.schemas.analysis import IncidentAnalysisResponse
from recallops.schemas.memory import RecalledMemoryResponse

if TYPE_CHECKING:
    from recallops.models.incident import Incident


@dataclass(frozen=True)
class IncidentAnalysisInput:
    """The incident fields an AI provider may analyze or embed."""

    incident_id: UUID
    title: str
    description: str
    service: str
    environment: str
    status: str


def build_incident_analysis_input(incident: "Incident") -> IncidentAnalysisInput:
    """Map a persisted incident onto the shared AI provider input.

    Shared by analysis and embedding so both features, and any future
    non-HTTP caller (e.g. a memory-extraction job), read incident content
    the same way.
    """

    return IncidentAnalysisInput(
        incident_id=incident.id,
        title=incident.title,
        description=incident.description,
        service=incident.service,
        environment=incident.environment,
        status=incident.status,
    )


class IncidentAnalysisService(Protocol):
    """Contract implemented by any incident analysis provider."""

    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        """Generate and validate an on-demand incident analysis."""

        ...


@dataclass(frozen=True)
class MemoryAssistedRecommendationResult:
    """Validated recommendation payload plus trusted provider metadata."""

    model_id: str
    payload: ModelMemoryAssistedRecommendationPayload


class MemoryAssistedRecommendationService(Protocol):
    """Contract implemented by memory-assisted recommendation providers."""

    def recommend(
        self,
        incident: IncidentAnalysisInput,
        memories: list[RecalledMemoryResponse],
    ) -> MemoryAssistedRecommendationResult:
        """Generate a recommendation grounded in bounded recalled memory context."""

        ...
