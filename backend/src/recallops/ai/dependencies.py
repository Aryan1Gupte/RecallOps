"""FastAPI dependencies for lazily selecting an AI provider."""

from collections.abc import Callable

from recallops.ai.bedrock import build_incident_analysis_service
from recallops.ai.protocols import IncidentAnalysisService

IncidentAnalysisServiceFactory = Callable[[], IncidentAnalysisService]


def get_incident_analysis_service_factory() -> IncidentAnalysisServiceFactory:
    """Return a factory so missing settings do not preempt incident lookup."""

    return build_incident_analysis_service
