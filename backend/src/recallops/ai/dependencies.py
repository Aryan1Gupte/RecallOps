"""FastAPI dependencies for lazily selecting an AI provider."""

from collections.abc import Callable

from recallops.ai.bedrock import build_incident_analysis_service
from recallops.ai.protocols import IncidentAnalysisService
from recallops.ai.titan import BedrockTitanEmbeddingService, build_embedding_service

IncidentAnalysisServiceFactory = Callable[[], IncidentAnalysisService]
EmbeddingServiceFactory = Callable[[], BedrockTitanEmbeddingService]


def get_incident_analysis_service_factory() -> IncidentAnalysisServiceFactory:
    """Return a factory so missing settings do not preempt incident lookup."""

    return build_incident_analysis_service


def get_embedding_service_factory() -> EmbeddingServiceFactory:
    """Return a factory so missing settings do not preempt the embedding preview."""

    return build_embedding_service
