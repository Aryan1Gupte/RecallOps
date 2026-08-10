"""FastAPI dependencies for lazily selecting an AI provider."""

from collections.abc import Callable

from recallops.ai.bedrock import (
    build_incident_analysis_service,
    build_memory_assisted_recommendation_service,
)
from recallops.ai.embedding_protocols import EmbeddingService
from recallops.ai.protocols import (
    IncidentAnalysisService,
    MemoryAssistedRecommendationService,
)
from recallops.ai.titan import build_embedding_service

IncidentAnalysisServiceFactory = Callable[[], IncidentAnalysisService]
EmbeddingServiceFactory = Callable[[], EmbeddingService]
MemoryAssistedRecommendationServiceFactory = Callable[
    [],
    MemoryAssistedRecommendationService,
]


def get_incident_analysis_service_factory() -> IncidentAnalysisServiceFactory:
    """Return a factory so missing settings do not preempt incident lookup."""

    return build_incident_analysis_service


def get_embedding_service_factory() -> EmbeddingServiceFactory:
    """Return a factory so missing settings do not preempt the embedding preview."""

    return build_embedding_service


def get_memory_assisted_recommendation_service_factory() -> MemoryAssistedRecommendationServiceFactory:
    """Return a factory so missing settings do not preempt incident lookup."""

    return build_memory_assisted_recommendation_service
