"""Provider-neutral incident analysis boundary."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from recallops.schemas.analysis import IncidentAnalysisResponse


@dataclass(frozen=True)
class IncidentAnalysisInput:
    """The incident fields an AI provider may analyze."""

    incident_id: UUID
    title: str
    description: str
    service: str
    environment: str
    status: str


class IncidentAnalysisService(Protocol):
    """Contract implemented by any incident analysis provider."""

    def analyze(self, incident: IncidentAnalysisInput) -> IncidentAnalysisResponse:
        """Generate and validate an on-demand incident analysis."""

        ...
